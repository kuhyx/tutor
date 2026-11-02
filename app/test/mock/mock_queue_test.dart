import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/mock/mock_queue.dart';
import 'package:tutor/storage/kv_store.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/services.dart';
import 'mock_fixtures.dart';

void main() {
  test('answers wait offline and replay in tap order', () async {
    var clock = 100;
    final q = MockAnswerQueue(MemoryKv(), now: () => clock++);
    await q.enqueue('m', 'q1', '0');
    await q.enqueue('m', 'q2', '3');
    final sent = <String>[];
    var up = false;
    Future<bool> send(QueuedAnswer a) async {
      if (!up) return false;
      sent.add('${a.task}@${a.ts}');
      return true;
    }

    expect(await q.flush(send), 2);
    expect(await q.pending(), hasLength(2));
    up = true;
    expect(await q.flush(send), 0);
    expect(sent, ['q1@100', 'q2@101']);
  });

  test('a failure keeps the rest and the order', () async {
    final q = MockAnswerQueue(MemoryKv());
    for (final t in ['a', 'b', 'c']) {
      await q.enqueue('m', t, 'x');
    }
    var calls = 0;
    final left = await q.flush((a) async => ++calls < 2);
    expect(left, 2);
    expect((await q.pending()).map((a) => a.task), ['b', 'c']);
  });

  test('a flush already running is joined', () async {
    final q = MockAnswerQueue(MemoryKv());
    await q.enqueue('m', 'a', 'x');
    var calls = 0;
    Future<bool> slow(QueuedAnswer a) async {
      calls++;
      await Future<void>.delayed(const Duration(milliseconds: 5));
      return true;
    }

    final both = await Future.wait([q.flush(slow), q.flush(slow)]);
    expect(both, [0, 0]);
    expect(calls, 1);
  });

  test('a broken store reads as empty', () async {
    final kv = MemoryKv()..data['mock.answers'] = 'not json';
    expect(await MockAnswerQueue(kv).pending(), isEmpty);
  });

  test('the relay sender writes the req under the stored rid', () async {
    final db = FakeRtdb();
    final s = services(db, FakeStream());
    final q = MockAnswerQueue(s.kv, now: () => 42);
    final a = await q.enqueue('m1', 'q1', '2');
    expect(await relayAnswerSender(s.relay)(a), isTrue);
    expect(mockBodies(db).single, {
      'op': 'answer',
      'mock_id': 'm1',
      'task': 'q1',
      'answer': '2',
      'ts': 42,
    });
    db.offline = true;
    expect(await relayAnswerSender(s.relay)(a), isFalse);
  });
}
