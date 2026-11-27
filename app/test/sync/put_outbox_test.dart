// Offline-first client writes (~/.claude/rules/offline-first.instructions.md):
// a PUT lands on this install first and is pushed when the database answers.
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/feedback/feedback_sender.dart';
import 'package:tutor/home/remote_bits.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/put_outbox.dart';
import 'package:tutor/util/ulid.dart';

import '../support/fake_rtdb.dart';

const _root = 'tutor/v1-e2e';

void main() {
  test(
    'an offline write is kept, survives a restart, is pushed later',
    () async {
      final db = FakeRtdb()..offline = true;
      final kv = MemoryKv();
      final box = PutOutbox(db.client(), kv);
      await box.put('$_root/prefs/current_subject', 'car');
      await box.put('$_root/feedback/f1', {'text': 'x'});
      await box.put('$_root/prefs/current_subject', 'garden');
      expect(await box.flush(), 0);
      expect(await box.pendingAt('$_root/prefs/current_subject'), 'garden');

      final again = PutOutbox(db.client(), kv);
      expect((await again.pending()).keys, [
        '$_root/feedback/f1',
        '$_root/prefs/current_subject',
      ]);
      db.offline = false;
      expect(await again.flush(), 2);
      expect(getAt(db.root, '$_root/prefs/current_subject'), 'garden');
      expect(getAt(db.root, '$_root/feedback/f1'), {'text': 'x'});
      expect(await again.pending(), isEmpty);
      expect(await again.flush(), 0);
      box.dispose();
      again.dispose();
    },
  );

  test('a failed push retries by itself with backoff', () async {
    final db = FakeRtdb()..offline = true;
    final box = PutOutbox(
      db.client(),
      MemoryKv(),
      retryAfter: const Duration(milliseconds: 20),
    );
    await box.put('$_root/prefs/current_subject', 'car');
    await Future<void>.delayed(const Duration(milliseconds: 30));
    expect(await box.pending(), isNotEmpty);
    db.offline = false;
    for (var i = 0; i < 50 && (await box.pending()).isNotEmpty; i++) {
      await Future<void>.delayed(const Duration(milliseconds: 20));
    }
    expect(getAt(db.root, '$_root/prefs/current_subject'), 'car');
    box.dispose();
  });

  test('picking a subject offline is kept and read back', () async {
    final db = FakeRtdb()..offline = true;
    final box = PutOutbox(db.client(), MemoryKv());
    await setCurrentSubject(box, 'car');
    expect(await box.pendingAt('$_root/prefs/current_subject'), 'car');
    expect(() => setCurrentSubject(box, 'B A D'), throwsArgumentError);
    box.dispose();
  });

  test('a report written offline is kept and sent once online', () async {
    final db = FakeRtdb()..offline = true;
    final box = PutOutbox(db.client(), MemoryKv());
    final sender = FeedbackSender(
      outbox: box,
      dev: '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10',
      ulid: UlidGenerator(),
      now: () => 42,
    );
    final fid = await sender.send(
      category: FeedbackCategory.ui,
      text: 'offline report',
      route: '/',
    );
    expect(
      (await box.pendingAt('$_root/feedback/$fid'))! as Map,
      containsPair('at', 42),
    );
    db.offline = false;
    expect(await box.flush(), 1);
    expect(
      (getAt(db.root, '$_root/feedback/$fid')! as Map)['text'],
      'offline report',
    );
    box.dispose();
  });

  test('coming back on screen pushes queued writes', () async {
    final binding = TestWidgetsFlutterBinding.ensureInitialized()
      ..handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    final db = FakeRtdb()..offline = true;
    final box = PutOutbox(db.client(), MemoryKv())
      ..flushOnShow(binding: binding)
      ..flushOnShow(binding: binding); // once only
    await box.put('$_root/prefs/current_subject', 'car');
    await pumpEventQueue(); // its own push fails offline
    db.offline = false;
    binding
      ..handleAppLifecycleStateChanged(AppLifecycleState.inactive)
      ..handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await pumpEventQueue();
    expect(getAt(db.root, '$_root/prefs/current_subject'), 'car');
    expect(db.log.where((l) => l.startsWith('PUT')), hasLength(1));
    box.dispose();
  });

  test('an unreadable queue reads as empty', () async {
    final kv = MemoryKv();
    final box = PutOutbox(FakeRtdb().client(), kv);
    for (final raw in ['not json', '[1]']) {
      await kv.set('outbox.puts', raw);
      expect(await box.pending(), isEmpty);
    }
  });
}
