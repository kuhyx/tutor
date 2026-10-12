import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/util/ulid.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';

const _dev = '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10';

void main() {
  late FakeRtdb db;
  late FakeStream stream;
  late RequestRunner runner;

  setUp(() {
    db = FakeRtdb();
    stream = FakeStream();
    runner = RequestRunner(
      RequestRelay(
        client: db.client(),
        stream: stream,
        dev: _dev,
        ulid: UlidGenerator(),
      ),
    );
  });

  StreamController<RtdbEvent> lastListen() => stream.listens.values.last;

  test('run follows to done; busy while working', () async {
    expect(runner.busy, isFalse);
    expect(() => runner.retry(), throwsStateError);
    final done = runner.run(RequestBody.stop('20261012-170448-5b71'));
    await Future<void>.delayed(Duration.zero);
    expect(runner.busy, isTrue);
    lastListen().add(
      const RtdbPut('/claim', {
        'by': _dev,
        'lease_until': 1,
        'attempt': 1,
        'phase': 'thinking',
        'at': 1,
      }),
    );
    await Future<void>.delayed(Duration.zero);
    expect(runner.status.value, isA<RelayWorking>());
    expect(runner.busy, isTrue);
    lastListen().add(
      const RtdbPut('/result', {
        'ok': true,
        'at': 2,
        'data': <String, Object>{},
      }),
    );
    expect(await done, isA<RelayDone>());
    expect(runner.canRetry, isFalse);
    runner.clear();
    expect(runner.status.value, isNull);
    await runner.dispose();
  });

  test('not sent -> retry re-PUTs the same rid', () async {
    db.offline = true;
    final first = await runner.run(RequestBody.next('20261012-170448-5b71'));
    expect(first, isA<RelayNotSent>());
    expect(runner.canRetry, isTrue);
    db.offline = false;
    final again = runner.retry();
    await Future<void>.delayed(Duration.zero);
    final rids = db.log.map((l) => l.split('/')[3]).toSet();
    expect(rids, hasLength(1));
    lastListen().add(
      const RtdbPut('/result', {
        'ok': false,
        'at': 2,
        'code': 'model_error',
        'error': 'x',
        'retry': true,
      }),
    );
    expect(await again, isA<RelayFailed>());
    expect(runner.canRetry, isTrue);
    await runner.dispose();
  });

  test('a newer run settles the older await', () async {
    final first = runner.run(RequestBody.stop('20261012-170448-5b71'));
    await Future<void>.delayed(Duration.zero);
    final second = runner.run(RequestBody.stop('20261012-170448-5b71'));
    expect(await first, isA<RelayQueued>());
    await runner.dispose();
    expect(await second, isA<RelayQueued>());
    expect(Phase.thinking.wire, 'thinking');
  });
}
