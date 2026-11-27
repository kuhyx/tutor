// Offline-first History: the kept copy, its byte budget, the archive queue
// and the kept-then-live stream (~/.claude/rules/offline-first.instructions.md).
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/history/history.dart';
import 'package:tutor/history/history_store.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_client.dart';

import '../model/samples.dart';
import '../support/fake_rtdb.dart';

const _a = '20261010-100000-aaaa';
const _b = '20261011-100000-bbbb';
const _root = 'tutor/v1-e2e';

FakeRtdb _db() {
  var root = setAt(null, '$_root/session_index', {_a: indexRow});
  root = setAt(root, '$_root/sessions/$_a', {
    'meta': sessionMeta,
    'msgs': {'m0001': tutorMessage},
  });
  return FakeRtdb()..root = root;
}

void main() {
  test(
    'list and transcript are kept and read offline after a restart',
    () async {
      final db = _db();
      final kv = MemoryKv();
      final repo = HistoryRepo(db.client(), kv);
      expect(await repo.kept(), isNull);
      expect(await repo.keptTranscript(_a), isNull);
      await repo.load();
      await repo.transcript(_a);

      db.offline = true;
      final again = HistoryRepo(db.client(), kv);
      expect((await again.kept())!.single.sid, _a);
      final t = (await again.keptTranscript(_a))!;
      expect(t.view.messages.single.key, 'm0001');
      await expectLater(again.load(), throwsA(isA<RtdbError>()));
    },
  );

  test(
    'archive lands locally, survives a failed push, is pushed later',
    () async {
      final db = _db();
      final kv = MemoryKv();
      final repo = HistoryRepo(db.client(), kv);
      await repo.load();
      await repo.transcript(_a);

      db.offline = true;
      await repo.setArchived(_a, archived: true);
      expect((await repo.kept())!.single.archived, isTrue);
      expect((await repo.keptTranscript(_a))!.archived, isTrue);
      expect(await repo.flush(), 0);
      expect(await repo.store.pending(), {_a: true});

      db.offline = false;
      expect(await repo.flush(), 1);
      expect(getAt(db.root, '$_root/sessions/$_a/user/archived'), isTrue);
      expect(await repo.store.pending(), isEmpty);
      expect(await repo.flush(), 0);
    },
  );

  test(
    'a flag that cannot be pushed still overrides the live answer',
    () async {
      final db = _db();
      final repo = HistoryRepo(db.client(), MemoryKv());
      db.failPrefix = '/$_root/sessions/$_b/user';
      await repo.setArchived(_b, archived: true);
      await repo.load();
      final kept = (await repo.store.list())!;
      expect(kept.users[_b], {'archived': true});
      final t = await repo.transcript(_b);
      expect(t.archived, isTrue);
      expect((await repo.store.transcript(_b))!['user'], {'archived': true});
      expect(await repo.store.pending(), {_b: true});
    },
  );

  test('coming back on screen pushes queued flags', () async {
    final binding = TestWidgetsFlutterBinding.ensureInitialized()
      ..handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    final db = _db();
    final repo = HistoryRepo(db.client(), MemoryKv())
      ..flushOnShow(binding: binding)
      ..flushOnShow(binding: binding); // once only
    db.offline = true;
    await repo.setArchived(_a, archived: true);
    await pumpEventQueue(); // its own push fails offline
    db.offline = false;
    binding
      ..handleAppLifecycleStateChanged(AppLifecycleState.inactive)
      ..handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await pumpEventQueue();
    expect(getAt(db.root, '$_root/sessions/$_a/user/archived'), isTrue);
    expect(db.log.where((l) => l.startsWith('PUT')), hasLength(1));
  });

  test('a newer flag stays queued when an older one lands', () async {
    final store = HistoryStore(MemoryKv());
    await store.archive(_a, archived: true);
    await store.archive(_a, archived: false);
    await store.pushed(_a, archived: true);
    expect(await store.pending(), {_a: false});
  });

  test('damaged entries read as nothing kept', () async {
    final kv = MemoryKv()
      ..data['history.list'] = '{bad'
      ..data['history.archive.queue'] = '[1]'
      ..data['history.transcripts'] = '{"$_a": [1, 2], "$_b": "x"}'
      ..data['history.transcript.$_a'] = '"not a map"';
    final store = HistoryStore(kv);
    expect(await store.list(), isNull);
    expect(await store.pending(), isEmpty);
    expect(await store.transcript(_a), isNull);
    expect(await store.transcript(_b), isNull);
    kv.data['history.list'] = '{"index": 1}';
    final list = (await store.list())!;
    expect(list.index, isEmpty);
    expect(list.users, isEmpty);
  });

  test('transcripts past the budget drop the oldest first', () async {
    final store = HistoryStore(MemoryKv(), budget: 40);
    final big = {'msgs': 'x' * 20}; // 31 characters as JSON
    await store.saveTranscript(_a, big);
    await store.saveTranscript(_b, big);
    expect(await store.transcript(_a), isNull);
    expect(await store.transcript(_b), big);
    await store.saveTranscript(_a, {'msgs': 'y' * 60}); // over the budget
    expect(await store.transcript(_a), isNull);
    expect(await store.transcript(_b), big);
  });

  test(
    'keptThenLive: kept first, then live or the kept copy offline',
    () async {
      Future<String> fails() async => throw const RtdbError('down');
      expect(
        await keptThenLive(
          () async => 'disk',
          () async => 'live',
        ).map((f) => (f.value, f.live, f.offline)).toList(),
        [('disk', false, false), ('live', true, false)],
      );
      expect(
        await keptThenLive(
          () async => 'disk',
          fails,
        ).map((f) => (f.value, f.offline)).toList(),
        [('disk', false), ('disk', true)],
      );
      await expectLater(
        keptThenLive(() async => null, fails).toList(),
        throwsA(isA<RtdbError>()),
      );
    },
  );
}
