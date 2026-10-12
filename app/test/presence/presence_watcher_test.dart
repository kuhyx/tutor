import 'dart:async';

import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/presence/presence_watcher.dart';
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

const Map<String, Object> _beat = {'host': 'pc', 'beat': 1};

void main() {
  test('snapshot = checking; beat = online; 75 s silence = offline', () {
    fakeAsync((async) {
      final s = _FakeStream();
      final w = PresenceWatcher(s)
        ..start()
        ..start();
      expect(s.paths, ['tutor/v1/presence/workers']);
      s.events!
        ..add(const RtdbConnected())
        ..add(const RtdbPut('/', {'dev1': _beat}));
      async.flushMicrotasks();
      expect(w.state.value, PcPresence.checking);
      async.elapse(const Duration(seconds: 30));
      s.events!.add(const RtdbPatch('/dev1', {'beat': 2}));
      async.flushMicrotasks();
      expect(w.state.value, PcPresence.online);
      // Keep-alive pings and drops are not beats.
      s.events!
        ..add(const RtdbKeepAlive())
        ..add(const RtdbDisconnected(null));
      async.elapse(const Duration(seconds: 74));
      expect(w.state.value, PcPresence.online);
      async.elapse(const Duration(seconds: 2));
      expect(w.state.value, PcPresence.offline);
      // A reconnect goes back to checking, then a beat brings it online.
      s.events!
        ..add(const RtdbConnected())
        ..add(const RtdbPut('/', {'dev1': _beat}))
        ..add(const RtdbPut('/dev1/beat', 3));
      async.flushMicrotasks();
      expect(w.state.value, PcPresence.online);
      unawaited(w.dispose());
      async.flushMicrotasks();
    });
  });

  test('no worker node, or a clean-exit DELETE, is offline at once', () {
    fakeAsync((async) {
      final s = _FakeStream();
      final w = PresenceWatcher(s)..start();
      s.events!
        ..add(const RtdbConnected())
        ..add(const RtdbPut('/', null));
      async.flushMicrotasks();
      expect(w.state.value, PcPresence.offline);
      s.events!
        ..add(const RtdbPut('/dev1', _beat))
        ..add(const RtdbCancel('x'))
        ..add(const RtdbAuthRevoked());
      async.flushMicrotasks();
      expect(w.state.value, PcPresence.online);
      s.events!.add(const RtdbPut('/dev1', null));
      async.flushMicrotasks();
      expect(w.state.value, PcPresence.offline);
      async.elapse(const Duration(minutes: 5));
      expect(w.state.value, PcPresence.offline);
      unawaited(w.stop());
      async.flushMicrotasks();
      expect(s.events!.hasListener, isFalse);
    });
  });
}
