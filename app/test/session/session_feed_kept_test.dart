// The Session screen is offline-first: the last session streamed is kept
// on this install, and a cold start with no network shows it at once.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/rtdb_event.dart';

import '../model/samples.dart';
import '../support/fake_stream.dart';

const _sid = '20261012-170448-5b71';
const _base = 'tutor/v1-e2e/sessions/$_sid';
const _live = 'tutor/v1-e2e/live';

/// A store whose writes fail (full or locked storage).
class _FullKv extends MemoryKv {
  @override
  Future<void> set(String key, String value) async =>
      throw StateError('storage full');
}

Future<void> _tick() => Future<void>.delayed(Duration.zero);

Future<SessionFeed> _online(KvStore kv) async {
  final stream = FakeStream();
  final feed = SessionFeed(stream, subject: 'automation', kv: kv)..start();
  await _tick();
  stream.listens[_live]!.add(
    const RtdbPut('/', {'session': _sid, 'subject': 'automation'}),
  );
  await _tick();
  stream.listens[_base]!
    ..add(const RtdbPut('/meta', sessionMeta))
    ..add(const RtdbPut('/msgs', {'m0001': tutorMessage}))
    ..add(const RtdbPatch('/progress', {'rid': 'r'}));
  await _tick();
  return feed;
}

void main() {
  test('a cold start offline shows the last session streamed', () async {
    final kv = MemoryKv();
    await (await _online(kv)).dispose();
    final cold = SessionFeed(FakeStream(), subject: 'automation', kv: kv)
      ..start();
    await _tick();
    final view = cold.view.value!;
    expect(view.sid, _sid);
    expect(view.meta!.n, 14);
    expect(view.messages.map((m) => m.key), ['m0001']);
    expect(view.progress, isNull); // a live trace is never kept
    await cold.dispose();
  });

  test('the kept session is per subject', () async {
    final kv = MemoryKv();
    await (await _online(kv)).dispose();
    final other = SessionFeed(FakeStream(), subject: 'car', kv: kv)..start();
    await _tick();
    expect(other.view.value, isNull);
    await other.dispose();
  });

  test('a stream that answers first wins over the kept copy', () async {
    final kv = MemoryKv();
    await (await _online(kv)).dispose();
    final feed = await _online(kv);
    expect(feed.view.value!.messages, hasLength(1));
    await feed.dispose();
  });

  test('an unreadable kept copy shows nothing', () async {
    final kv = MemoryKv()..data['session.last.automation'] = '{"sid": 3}';
    final feed = SessionFeed(FakeStream(), subject: 'automation', kv: kv)
      ..start();
    await _tick();
    expect(feed.view.value, isNull);
    kv.data['session.last.automation'] = '{broken';
    final again = SessionFeed(FakeStream(), subject: 'automation', kv: kv)
      ..start();
    await _tick();
    expect(again.view.value, isNull);
    await feed.dispose();
    await again.dispose();
  });

  test('a failed write keeps the live screen going', () async {
    final feed = await _online(_FullKv());
    expect(feed.view.value!.messages, hasLength(1));
    await feed.dispose();
  });
}
