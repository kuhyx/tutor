import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/rev_watcher.dart';
import 'package:tutor/sync/rtdb_client.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/sync/rtdb_stream.dart';

class _FakeStream implements RtdbStream {
  StreamController<RtdbEvent>? events;
  final paths = <String>[];

  @override
  RtdbClient get client => throw UnimplementedError();

  @override
  Stream<RtdbEvent> listen(
    String path, {
    Map<String, String> query = const {},
  }) {
    paths.add(path);
    return (events = StreamController<RtdbEvent>()).stream;
  }
}

void main() {
  final binding = TestWidgetsFlutterBinding.ensureInitialized();

  setUp(
    () => binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed),
  );

  test('catalogRev and foregroundFor', () {
    expect(catalogRev(null), 0);
    expect(catalogRev(const {'stats': 3}), 0);
    expect(catalogRev(const {'catalog': 'x'}), 0);
    expect(catalogRev(const {'catalog': 7.0}), 7);
    expect(foregroundFor(null), isTrue);
    expect(foregroundFor(AppLifecycleState.resumed), isTrue);
    expect(foregroundFor(AppLifecycleState.inactive), isNull);
    for (final s in [
      AppLifecycleState.hidden,
      AppLifecycleState.paused,
      AppLifecycleState.detached,
    ]) {
      expect(foregroundFor(s), isFalse);
    }
  });

  test(
    'emits real catalog moves only; reconnect snapshots are ignored',
    () async {
      final s = _FakeStream();
      final w = RevWatcher(s);
      final seen = <int>[];
      final sub = w.catalogChanges.listen(seen.add);
      expect(s.paths, ['tutor/v1/rev']);
      s.events!
        ..add(const RtdbConnected())
        ..add(const RtdbPut('/', {'catalog': 7, 'stats': 3}))
        ..add(const RtdbPatch('/', {'stats': 4}))
        ..add(const RtdbKeepAlive())
        ..add(const RtdbPut('/catalog', 8))
        // A reconnect resends the whole node, unchanged: not a move.
        ..add(const RtdbDisconnected(null))
        ..add(const RtdbConnected())
        ..add(const RtdbPut('/', {'catalog': 8, 'stats': 4}))
        ..add(const RtdbPatch('/', {'catalog': 9}));
      await pumpEventQueue();
      expect(seen, [8, 9]);
      await sub.cancel();
      await w.dispose();
    },
  );

  test(
    'ref-counted: one listen for many screens, closed by the last',
    () async {
      final s = _FakeStream();
      final w = RevWatcher(s);
      final a = w.catalogChanges.listen((_) {});
      final b = w.catalogChanges.listen((_) {});
      expect(s.paths, hasLength(1));
      await a.cancel();
      expect(w.listening, isTrue);
      await b.cancel();
      expect(w.listening, isFalse);
      expect(s.events!.hasListener, isFalse);
      // The baseline survives: a move seen on the next listen is emitted.
      final seen = <int>[];
      final c = w.catalogChanges.listen(seen.add);
      expect(s.paths, hasLength(2));
      s.events!.add(const RtdbPut('/', {'catalog': 1}));
      await pumpEventQueue();
      expect(seen, isEmpty); // first value ever = baseline
      await c.cancel();
      await w.dispose();
    },
  );

  test(
    'pauses in the back, resumes in front; a missed move is emitted',
    () async {
      final s = _FakeStream();
      // Without listeners, coming to the front opens nothing.
      final w = RevWatcher(s)..foreground(visible: true);
      expect(s.paths, isEmpty);
      final seen = <int>[];
      final sub = w.catalogChanges.listen(seen.add);
      s.events!.add(const RtdbPut('/', {'catalog': 7}));
      await pumpEventQueue();
      final first = s.events!;
      binding
        ..handleAppLifecycleStateChanged(AppLifecycleState.inactive)
        ..handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      await pumpEventQueue();
      expect(w.listening, isFalse);
      expect(first.hasListener, isFalse);
      binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      expect(w.listening, isFalse); // inactive alone decides nothing
      binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      expect(w.listening, isTrue);
      expect(s.paths, hasLength(2));
      s.events!
        ..add(const RtdbConnected())
        ..add(const RtdbPut('/', {'catalog': 9}));
      await pumpEventQueue();
      expect(seen, [9]);
      // `cancel` ends the listen; the next return to the front reopens it.
      await s.events!.close();
      await pumpEventQueue();
      expect(w.listening, isFalse);
      w.foreground(visible: true);
      expect(s.paths, hasLength(3));
      await sub.cancel();
      await w.dispose();
    },
  );

  test('opened while hidden: waits for the front', () async {
    binding
      ..handleAppLifecycleStateChanged(AppLifecycleState.inactive)
      ..handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    final s = _FakeStream();
    final w = RevWatcher(s, binding: binding);
    final sub = w.catalogChanges.listen((_) {});
    expect(s.paths, isEmpty);
    binding
      ..handleAppLifecycleStateChanged(AppLifecycleState.inactive)
      ..handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    expect(s.paths, hasLength(1));
    await w.dispose();
    await sub.cancel();
  });
}
