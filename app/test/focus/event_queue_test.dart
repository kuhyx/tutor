import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/focus/event_queue.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/util/ulid.dart';

void main() {
  late MemoryKv kv;
  late FocusEventQueue queue;
  var clock = 1000;

  FocusEventQueue open() => FocusEventQueue(
    kv,
    ulid: UlidGenerator(now: () => clock),
    now: () => clock,
  );

  setUp(() {
    kv = MemoryKv();
    clock = 1000;
    queue = open();
  });

  test('enqueue keeps the tap time and mints a rid at tap time', () async {
    final a = await queue.enqueue('start');
    clock = 5000;
    final b = await queue.enqueue('checkin', ts: 4200);
    expect(a.ts, 1000);
    expect(b.ts, 4200);
    expect(a.platform, 'phone');
    expect(a.rid, hasLength(26));
    expect(a.rid.compareTo(b.rid), lessThan(0));
    expect((await queue.pending()).map((e) => e.event), ['start', 'checkin']);
  });

  test('survives a restart: same rid, same ts', () async {
    final a = await queue.enqueue('start');
    final reopened = open();
    final back = (await reopened.pending()).single;
    expect(back.rid, a.rid);
    expect(back.ts, a.ts);
    expect(back.event, 'start');
  });

  test('rejects an unknown event name', () {
    expect(() => queue.enqueue('pause'), throwsArgumentError);
  });

  test('flush sends in order and empties the queue', () async {
    await queue.enqueue('start');
    await queue.enqueue('checkin');
    await queue.enqueue('stop');
    final seen = <String>[];
    final r = await queue.flush((e) async {
      seen.add(e.event);
      return FocusSendOutcome.sent;
    });
    expect(seen, ['start', 'checkin', 'stop']);
    expect(r.sent, 3);
    expect(r.left, 0);
    expect(await queue.pending(), isEmpty);
  });

  test('a retry outcome stops the flush and keeps the rest in order', () async {
    await queue.enqueue('start');
    await queue.enqueue('checkin');
    await queue.enqueue('stop');
    var calls = 0;
    final r = await queue.flush((e) async {
      calls++;
      return calls == 1 ? FocusSendOutcome.sent : FocusSendOutcome.retry;
    });
    expect(calls, 2);
    expect(r.sent, 1);
    expect(r.left, 2);
    expect((await queue.pending()).map((e) => e.event), ['checkin', 'stop']);
  });

  test('a refused event is dropped, later ones still go', () async {
    await queue.enqueue('checkin');
    await queue.enqueue('stop');
    final r = await queue.flush(
      (e) async => e.event == 'checkin'
          ? FocusSendOutcome.refused
          : FocusSendOutcome.sent,
    );
    expect(r.dropped, 1);
    expect(r.sent, 1);
    expect(await queue.pending(), isEmpty);
  });

  test('a throwing sender keeps progress made so far', () async {
    await queue.enqueue('start');
    await queue.enqueue('checkin');
    var calls = 0;
    await expectLater(
      queue.flush((e) async {
        if (++calls == 2) throw StateError('network');
        return FocusSendOutcome.sent;
      }),
      throwsStateError,
    );
    expect((await queue.pending()).map((e) => e.event), ['checkin']);
  });

  test('overlapping flushes send each event once', () async {
    await queue.enqueue('start');
    var sends = 0;
    Future<FocusSendOutcome> send(QueuedFocusEvent e) async {
      sends++;
      await Future<void>.delayed(const Duration(milliseconds: 5));
      return FocusSendOutcome.sent;
    }

    final results = await Future.wait([queue.flush(send), queue.flush(send)]);
    expect(sends, 1);
    expect(results.map((r) => r.sent).reduce((a, b) => a + b), 1);
  });

  test('events enqueued during a flush are kept', () async {
    await queue.enqueue('start');
    final r = await queue.flush((e) async {
      await queue.enqueue('checkin');
      return FocusSendOutcome.sent;
    });
    expect(r.sent, 1);
    expect((await queue.pending()).map((e) => e.event), ['checkin']);
  });

  test('a corrupt store reads as empty', () async {
    await kv.set('focus_events', '{not json');
    expect(await queue.pending(), isEmpty);
    await queue.enqueue('start');
    expect(await queue.pending(), hasLength(1));
  });
}
