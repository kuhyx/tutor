import 'dart:async';

import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/focus/checkin_notifier.dart';
import 'package:tutor/focus/event_queue.dart';
import 'package:tutor/focus/focus_timer.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/util/ulid.dart';

class _Notifier implements FocusCheckinNotifier {
  final List<Duration> scheduled = [];
  int cancelled = 0;
  final StreamController<int> taps = StreamController<int>.broadcast();
  List<int> pending = [];

  @override
  Future<void> schedule(Duration after) async => scheduled.add(after);

  @override
  Future<void> cancel() async => cancelled++;

  @override
  Stream<int> get confirmations => taps.stream;

  @override
  Future<List<int>> takePending() async {
    final out = pending;
    pending = [];
    return out;
  }
}

void main() {
  late MemoryKv kv;
  late _Notifier notifier;
  late FocusEventQueue queue;
  late bool online;
  late List<String> sent;
  var clock = 0;

  const min = 60000;

  FocusTimer open() => FocusTimer(
    kv: kv,
    queue: queue,
    send: (e) async {
      if (!online) return FocusSendOutcome.retry;
      sent.add('${e.event}@${e.ts}');
      return FocusSendOutcome.sent;
    },
    notifier: notifier,
    now: () => clock,
  );

  setUp(() {
    kv = MemoryKv();
    notifier = _Notifier();
    clock = 1000 * min;
    online = true;
    sent = [];
    queue = FocusEventQueue(
      kv,
      ulid: UlidGenerator(now: () => clock),
      now: () => clock,
    );
  });

  test('start, check-ins and stop count the gaps and arm the prompt', () async {
    final t = open();
    await t.load();
    expect(t.isRunning, isFalse);
    await t.start();
    expect(t.isRunning, isTrue);
    expect(notifier.scheduled.last, checkinEvery);
    expect(checkinEvery, const Duration(minutes: 7));
    expect(notifier.scheduled.last, const Duration(minutes: 7));
    clock += 6 * min;
    expect(t.checkinDue, isFalse);
    clock += 1 * min;
    expect(t.checkinDue, isTrue);
    expect(t.counted, const Duration(minutes: 7));
    await t.checkin();
    expect(t.checkinDue, isFalse);
    clock += 4 * min;
    await t.stop();
    expect(t.counted, const Duration(minutes: 11));
    expect(t.isRunning, isFalse);
    expect(notifier.cancelled, 1);
    await t.flush();
    expect(sent, [
      'start@${1000 * min}',
      'checkin@${1007 * min}',
      'stop@${1011 * min}',
    ]);
    t.dispose();
  });

  test('the ticker cancels the notifier once when the run lapses', () {
    fakeAsync((async) {
      // The queue's lock future must be born in the fake zone.
      queue = FocusEventQueue(
        kv,
        ulid: UlidGenerator(now: () => clock),
        now: () => clock,
      );
      final t = open();
      unawaited(t.load().then((_) => t.start()));
      async.flushMicrotasks();
      expect(notifier.cancelled, 0);
      clock += 10 * min;
      async.elapse(const Duration(seconds: 1));
      expect(notifier.cancelled, 0); // exactly 10 min is not yet a lapse
      clock += 1000;
      async.elapse(const Duration(seconds: 1));
      expect(t.isLapsed, isTrue);
      expect(notifier.cancelled, 1);
      clock += 5000;
      async.elapse(const Duration(seconds: 3));
      expect(notifier.cancelled, 1);
      unawaited(t.checkin()); // the way back; a new lapse cancels again
      async.flushMicrotasks();
      clock += 10 * min + 1000;
      async.elapse(const Duration(seconds: 1));
      expect(notifier.cancelled, 2);
      t.dispose();
    });
  });

  test('a missed check-in stops the counting; the next tap restarts', () async {
    final t = open();
    await t.start();
    clock += 11 * min;
    expect(t.isLapsed, isTrue);
    expect(t.counted, Duration.zero);
    await t.checkin();
    expect(t.isRunning, isTrue);
    await t.flush();
    expect(sent, ['start@${1000 * min}', 'start@${1011 * min}']);
    t.dispose();
  });

  test('offline taps queue with their own times and go out in order', () async {
    online = false;
    final t = open();
    await t.start();
    clock += 5 * min;
    await t.checkin();
    clock += 30 * min;
    await t.flush();
    expect(sent, isEmpty);
    expect((await queue.pending()).length, 2);
    online = true;
    await t.flush();
    expect(sent, ['start@${1000 * min}', 'checkin@${1005 * min}']);
    t.dispose();
  });

  test('a run survives a restart; off-screen taps are checked in', () async {
    final first = open();
    await first.start();
    first.dispose();
    clock += 8 * min;
    notifier.pending = [clock - 2 * min];
    final second = open();
    await second.load();
    expect(second.isRunning, isTrue);
    await second.flush();
    expect(sent.last, 'checkin@${1006 * min}');
    expect(second.counted, const Duration(minutes: 6 + 2));
    second.dispose();
  });

  test('a tap on the notification while the app is open checks in', () async {
    final t = open();
    await t.load();
    await t.start();
    clock += 5 * min;
    notifier.taps.add(clock);
    await Future<void>.delayed(Duration.zero);
    await t.flush();
    expect(sent.last, 'checkin@${1005 * min}');
    t.dispose();
  });

  test('stop with nothing running does nothing', () async {
    final t = open();
    await t.stop();
    expect(await queue.pending(), isEmpty);
    t.dispose();
  });
}
