import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/util/ulid.dart';

import '../../tool/fixture/fixture_stream.dart';
import '../support/fake_rtdb.dart';

void main() {
  test('stand-in PC answers every request sent over the shared hub', () async {
    final db = FakeRtdb();
    final client = db.client();
    final stream = FixtureStream(
      client,
      () => db.root,
      worker: (kind, body) => {
        'ok': true,
        'at': 1,
        'data': {'kind': kind},
      },
    );
    final relay = RequestRelay(
      client: client,
      stream: stream,
      dev: '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10',
      ulid: UlidGenerator(),
    );
    // Two in a row: the second joins the hub's open listen.
    for (var i = 0; i < 2; i++) {
      final last = await relay
          .send(RequestBody.focusStatus())
          .last
          .timeout(const Duration(seconds: 3));
      expect(last, isA<RelayDone>());
    }
  });
}
