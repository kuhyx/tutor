import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/focus/event_queue.dart';
import 'package:tutor/focus/focus_timer.dart';
import 'package:tutor/model/card.dart';
import 'package:tutor/review/review_items.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/util/ulid.dart';

import '../model/samples.dart';

final _item = ReviewItem(
  subject: 'sql',
  subjectTitle: 'SQL',
  cardId: 'joins',
  card: StudyCard.fromJson(card),
);

void main() {
  late MemoryKv kv;
  late FocusEventQueue queue;
  late List<QueuedFocusEvent> sent;
  late List<ReviewItem?> offers;
  late int picks;
  var clock = 0;
  const min = 60000;

  FocusTimer open({bool picker = true}) => FocusTimer(
    kv: kv,
    queue: queue,
    send: (e) async {
      sent.add(e);
      return FocusSendOutcome.sent;
    },
    pick: picker
        ? () async {
            picks++;
            return offers.isEmpty ? null : offers.removeAt(0);
          }
        : null,
    now: () => clock,
  );

  List<String> wire() => [for (final e in sent) '${e.event}@${e.ts}'];

  setUp(() {
    kv = MemoryKv();
    clock = 1000 * min;
    sent = [];
    offers = [_item, _item, _item];
    picks = 0;
    queue = FocusEventQueue(
      kv,
      ulid: UlidGenerator(now: () => clock),
      now: () => clock,
    );
  });

  test('the 420 s prompt picks one card once; it replaces the tap', () async {
    final t = open();
    await t.load();
    await t.start();
    clock += 6 * min;
    await t.pickIfDue();
    expect((t.checkinCard, picks), (null, 0));
    clock += 1 * min;
    await t.pickIfDue();
    await t.pickIfDue();
    expect(t.checkinCard, same(_item));
    expect(picks, 1);
    expect(t.wantsTap, isFalse);
    t.dispose();
  });

  test('a rating within 600 s is a card beat at the answer time', () async {
    final t = open();
    await t.load();
    await t.start();
    clock += 7 * min;
    await t.pickIfDue();
    clock += 30000;
    await t.cardRated(clock);
    await t.flush();
    const at = 1000 * min + 7 * min + 30000;
    expect(wire(), ['start@${1000 * min}', 'card@$at']);
    expect((sent.last.subject, sent.last.card), ('sql', 'joins'));
    expect(t.checkinCard, isNull);
    expect(t.checkinDue, isFalse);
    expect(t.counted, const Duration(minutes: 7, seconds: 30));
    t.dispose();
  });

  test(
    'a rating under 1 s is graded but no beat; another card comes',
    () async {
      final t = open();
      await t.load();
      await t.start();
      clock += 7 * min;
      await t.pickIfDue();
      clock += 999;
      await t.cardRated(clock);
      await t.flush();
      expect(wire(), ['start@${1000 * min}']);
      expect(t.checkinCard, isNull);
      await t.pickIfDue();
      expect(t.checkinCard, same(_item));
      expect(picks, 2);
      t.dispose();
    },
  );

  test(
    'after the lapse the card stays; its rating starts a new segment',
    () async {
      final t = open();
      await t.load();
      await t.start();
      clock += 7 * min;
      await t.pickIfDue();
      clock += 3 * min + 50000; // 650 s
      expect(t.isLapsed, isTrue);
      expect(t.checkinCard, same(_item));
      await t.cardRated(clock);
      await t.flush();
      expect(wire(), ['start@${1000 * min}', 'start@$clock']);
      expect(t.isRunning, isTrue);
      t.dispose();
    },
  );

  test('no card (or no picker): the old tap, which sends checkin', () async {
    offers = [];
    for (final t in [open(), open(picker: false)]) {
      await t.load();
      await t.start();
      clock += 7 * min;
      await t.pickIfDue();
      expect((t.checkinCard, t.wantsTap), (null, true));
      await t.checkin();
      expect(t.wantsTap, isFalse);
      await t.stop();
      t.dispose();
    }
    await queue.flush((e) async {
      sent.add(e);
      return FocusSendOutcome.sent;
    });
    expect(sent.where((e) => e.event == 'checkin'), hasLength(2));
  });

  test('stop drops an unanswered card ungraded', () async {
    final t = open();
    await t.load();
    await t.start();
    clock += 7 * min;
    await t.pickIfDue();
    await t.stop();
    expect(t.checkinCard, isNull);
    await t.cardRated(clock + 5000);
    await t.flush();
    expect(wire(), ['start@${1000 * min}', 'stop@$clock']);
    t.dispose();
  });

  test('a restart drops the pick; the reopened run picks again', () async {
    final first = open();
    await first.load();
    await first.start();
    clock += 7 * min;
    await first.pickIfDue();
    first.dispose();
    final second = open();
    expect(second.checkinCard, isNull);
    await second.load();
    expect(second.checkinCard, same(_item));
    expect(picks, 2);
    second.dispose();
  });

  test(
    'a lapsed run reopened offers a card with the missed check-in',
    () async {
      final first = open();
      await first.load();
      await first.start();
      first.dispose();
      clock += 11 * min;
      final second = open();
      await second.load();
      expect(second.isLapsed, isTrue);
      expect(second.checkinCard, same(_item));
      second.dispose();
    },
  );
}
