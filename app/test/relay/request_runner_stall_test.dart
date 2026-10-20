// A request with no result and no progress for 3 minutes (fake time).
import 'dart:async';

import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/util/ulid.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/ui.dart' show lastRequest;

const _dev = '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10';

void main() {
  late FakeRtdb db;
  late FakeStream stream;

  setUp(() {
    db = FakeRtdb();
    stream = FakeStream();
  });

  /// Delivers [event] for the latest request (over the shared listen).
  void toLatest(RtdbEvent event) {
    final reqs = getAt(db.root, 'tutor/v1/requests')! as Map<String, dynamic>;
    final rid = (reqs.keys.toList()..sort()).last;
    expect(stream.emit('tutor/v1/requests/$rid', event), isTrue);
  }

  group('no reply from the PC', () {
    const sid = '20261012-170448-5b71';
    const working = RtdbPut('/claim', {
      'by': _dev,
      'lease_until': 1,
      'attempt': 1,
      'phase': 'thinking',
      'at': 1,
    });
    const result = RtdbPut('/result', {
      'ok': true,
      'at': 2,
      'data': <String, Object>{'msg': 'm0012'},
    });

    // Runs [body] under fake time: the runner is built inside, so its timer
    // and stream callbacks belong to the fake zone.
    void fake(void Function(FakeAsync async, RequestRunner r) body) =>
        fakeAsync((async) {
          final r = RequestRunner(
            RequestRelay(
              client: db.client(),
              stream: stream,
              dev: _dev,
              ulid: UlidGenerator(),
            ),
            stallAfter: sessionStallAfter,
          );
          body(async, r);
          unawaited(r.dispose());
          async.flushMicrotasks();
        });

    int rids() =>
        (getAt(db.root, 'tutor/v1/requests')! as Map<String, dynamic>).length;

    test('stalled after 3 minutes with no result or progress', () {
      fake((async, r) {
        unawaited(r.run(RequestBody.message(sid, 'power')));
        async.flushMicrotasks();
        expect(r.busy, isTrue);
        async.elapse(const Duration(minutes: 2, seconds: 59));
        expect(r.stalled.value, isFalse);
        async.elapse(const Duration(seconds: 1));
        expect(r.stalled.value, isTrue);
        expect(r.busy, isTrue, reason: 'still in flight, only Send reopens');
      });
    });

    test('a phase change is progress: the 3 minutes start over', () {
      fake((async, r) {
        unawaited(r.run(RequestBody.message(sid, 'power')));
        async
          ..flushMicrotasks()
          ..elapse(const Duration(minutes: 2, seconds: 59));
        toLatest(working);
        async
          ..flushMicrotasks()
          ..elapse(const Duration(minutes: 2, seconds: 59));
        expect(r.stalled.value, isFalse);
        async.elapse(const Duration(seconds: 1));
        expect(r.stalled.value, isTrue);
      });
    });

    test('a result clears it and stops the timer', () {
      fake((async, r) {
        unawaited(r.run(RequestBody.message(sid, 'power')));
        async
          ..flushMicrotasks()
          ..elapse(const Duration(minutes: 4));
        expect(r.stalled.value, isTrue);
        toLatest(result);
        async.flushMicrotasks();
        expect(r.busy, isFalse);
        expect(r.stalled.value, isFalse);
        expect(async.pendingTimers, isEmpty);
      });
    });

    test('send again with the same text keeps the rid: one reply', () {
      fake((async, r) {
        final first = r.run(RequestBody.message(sid, 'power'));
        async
          ..flushMicrotasks()
          ..elapse(const Duration(minutes: 3));
        expect(r.stalled.value, isTrue);
        final (rid, _) = lastRequest(db);
        final again = r.run(RequestBody.message(sid, 'power'));
        async.flushMicrotasks();
        expect(rids(), 1, reason: 'same rid: the worker dedupes it');
        expect(lastRequest(db).$1, rid);
        expect(r.stalled.value, isFalse, reason: 'a fresh 3 minutes');
        RelayStatus? a;
        RelayStatus? b;
        unawaited(first.then((s) => a = s));
        unawaited(again.then((s) => b = s));
        async.flushMicrotasks();
        expect(a, isNull, reason: 'the first caller is not settled early');
        // The reply that was only late arrives once, on the same rid.
        toLatest(result);
        async.flushMicrotasks();
        expect(a, isA<RelayDone>());
        expect(b, isA<RelayDone>());
      });
    });

    test('send again with other text is a new message: new rid', () {
      fake((async, r) {
        unawaited(r.run(RequestBody.message(sid, 'power')));
        async
          ..flushMicrotasks()
          ..elapse(const Duration(minutes: 3));
        final (rid, _) = lastRequest(db);
        unawaited(r.run(RequestBody.message(sid, 'power stroke')));
        async.flushMicrotasks();
        expect(rids(), 2);
        expect(lastRequest(db).$1, isNot(rid));
        expect(r.stalled.value, isFalse);
        // A late result for the abandoned rid changes nothing on screen.
        stream.emit('tutor/v1/requests/$rid', result);
        async.flushMicrotasks();
        expect(r.busy, isTrue);
      });
    });

    test('no stallAfter: never stalled, no timer', () {
      fakeAsync((async) {
        final r = RequestRunner(
          RequestRelay(
            client: db.client(),
            stream: stream,
            dev: _dev,
            ulid: UlidGenerator(),
          ),
        );
        unawaited(r.run(RequestBody.message(sid, 'power')));
        async
          ..flushMicrotasks()
          ..elapse(const Duration(hours: 1));
        expect(r.stalled.value, isFalse);
        expect(async.pendingTimers, isEmpty);
        unawaited(r.dispose());
        async.flushMicrotasks();
      });
    });

    test('not stalled: the same text is a plain new run', () {
      fake((async, r) {
        unawaited(r.run(RequestBody.message(sid, 'power')));
        async.flushMicrotasks();
        unawaited(r.run(RequestBody.message(sid, 'power')));
        async.flushMicrotasks();
        expect(rids(), 2);
      });
    });
  });
}
