import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/focus/checkin_notifier.dart';
import 'package:tutor/focus/event_queue.dart';
import 'package:tutor/focus/focus_timer.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/util/ulid.dart';

class _Notifier extends NoopCheckinNotifier {
  int cancelled = 0;

  @override
  Future<void> cancel() async => cancelled++;
}

void main() {
  const min = 60000;
  const grace = Duration(milliseconds: 80);
  late MemoryKv kv;
  late _Notifier notifier;
  late FocusEventQueue queue;
  late List<String> sent;
  var clock = 0;

  FocusTimer open() => FocusTimer(
    kv: kv,
    queue: queue,
    send: (e) async {
      sent.add('${e.event}@${e.ts}');
      return FocusSendOutcome.sent;
    },
    notifier: notifier,
    background: grace,
    now: () => clock,
  );

  Future<void> pastGrace() => Future<void>.delayed(grace * 3);

  setUp(() {
    kv = MemoryKv();
    notifier = _Notifier();
    clock = 1000 * min;
    sent = [];
    queue = FocusEventQueue(
      kv,
      ulid: UlidGenerator(now: () => clock),
      now: () => clock,
    );
  });

  test('away past the grace: stop with the moment it left', () async {
    final t = open();
    await t.start();
    clock += 3 * min;
    await t.leftForeground();
    clock += 5 * min; // the grace runs out much later in wall time
    await pastGrace();
    expect(t.isRunning, isFalse);
    expect(t.counted, const Duration(minutes: 3));
    expect(notifier.cancelled, 1);
    expect(sent, ['start@${1000 * min}', 'stop@${1003 * min}']);
    t.dispose();
  });

  test('back within the grace: still counting, nothing sent', () async {
    final t = open();
    await t.start();
    clock += min;
    await t.leftForeground();
    expect((await queue.pending()).last.event, 'stop');
    await t.returnedToForeground();
    await pastGrace();
    expect(t.isRunning, isTrue);
    expect(notifier.cancelled, 0);
    final events = (await queue.pending()).map((e) => e.event);
    expect(events, isNot(contains('stop')));
    expect(sent, ['start@${1000 * min}']);
    t.dispose();
  });

  test('the held stop is not flushed during the grace', () async {
    final t = open();
    await t.start();
    await t.leftForeground();
    await t.flush();
    expect(sent.where((s) => s.startsWith('stop')), isEmpty);
    await pastGrace();
    expect(sent.last, 'stop@${1000 * min}');
    t.dispose();
  });

  test('a killed process still delivers the stop on the next launch', () async {
    final first = open();
    await first.start();
    clock += 2 * min;
    await first.leftForeground();
    first.dispose(); // process dies inside the grace
    clock += 30 * min;
    queue = FocusEventQueue(kv, now: () => clock); // new process: nothing held
    final second = open();
    await second.load();
    await second.flush();
    expect(second.isRunning, isFalse);
    expect(second.isLapsed, isFalse);
    expect(sent, ['start@${1000 * min}', 'stop@${1002 * min}']);
    expect(notifier.cancelled, 1);
    second.dispose();
  });

  test('leaving with nothing running queues nothing', () async {
    final t = open();
    await t.load();
    await t.leftForeground();
    await pastGrace();
    expect(await queue.pending(), isEmpty);
    t.dispose();
  });

  test('detach stops at once without waiting for the grace', () async {
    final t = open();
    await t.start();
    clock += min;
    await t.leftForeground(commit: true);
    expect(t.isRunning, isFalse);
    await t.flush();
    expect(sent.last, 'stop@${1001 * min}');
    t.dispose();
  });

  test('leaving twice keeps the first moment', () async {
    final t = open();
    await t.start();
    clock += min;
    unawaited(t.leftForeground());
    clock += min;
    await t.leftForeground();
    await pastGrace();
    expect(sent.last, 'stop@${1001 * min}');
    t.dispose();
  });
}
