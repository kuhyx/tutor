import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/sync/rtdb_client.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/util/ulid.dart';

import '../support/fake_stream.dart';

const _dev = '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10';

void main() {
  late List<http.Request> puts;
  late bool failPut;
  late FakeStream stream;
  late RequestRelay relay;

  setUp(() {
    puts = [];
    failPut = false;
    stream = FakeStream();
    final client = RtdbClient(
      databaseUrl: 'https://db',
      idToken: () async => 't',
      httpClient: MockClient((req) async {
        if (failPut) throw http.ClientException('offline');
        puts.add(req);
        return http.Response(req.body, 200);
      }),
    );
    var now = 1791731346000;
    relay = RequestRelay(
      client: client,
      stream: stream,
      dev: _dev,
      ulid: UlidGenerator(now: () => now++),
      now: () => now,
    );
  });

  Future<void> pump() => Future<void>.delayed(Duration.zero);

  /// Delivers [event] for `requests/{rid}` (over the shared listen).
  void feed(String rid, RtdbEvent event) =>
      expect(stream.emit('tutor/v1/requests/$rid', event), isTrue);

  test('PUTs only req, then follows claim phases to the result', () async {
    final pending = relay.prepare(
      RequestBody.message('20261012-170448-5b71', 'hi'),
    );
    final statuses = <RelayStatus>[];
    final done = relay.resend(pending).listen(statuses.add).asFuture<void>();
    await pump();
    expect(puts.single.url.path, '/tutor/v1/requests/${pending.rid}/req.json');
    final body = jsonDecode(puts.single.body) as Map<String, dynamic>;
    expect(body['created'], {'.sv': 'timestamp'});
    expect(body['sent_at'], pending.req.sentAt);
    expect(body['dev'], _dev);

    void events(RtdbEvent e) => feed(pending.rid, e);
    Map<String, Object> claim(String phase) => {
      'by': 'w',
      'lease_until': 9,
      'attempt': 1,
      'phase': phase,
      'at': 1,
    };
    events(const RtdbConnected());
    events(RtdbPut('/', {'req': body}));
    events(RtdbPut('/claim', claim('claimed')));
    events(RtdbPut('/claim', claim('claimed'))); // duplicate: not re-emitted
    events(const RtdbPatch('/claim', {'phase': 'thinking'}));
    events(
      const RtdbPut('/result', {
        'ok': true,
        'at': 2,
        'data': {'msg': 'm0012'},
      }),
    );
    await done;
    expect(statuses.map((s) => s.runtimeType), [
      RelayQueued,
      RelayWorking,
      RelayWorking,
      RelayDone,
    ]);
    expect((statuses[2] as RelayWorking).phase, Phase.thinking);
    expect((statuses.last as RelayDone).data, {'msg': 'm0012'});
  });

  test(
    'a failed PUT is NotSent; retry re-PUTs the same rid and sent_at',
    () async {
      final pending = relay.prepare(RequestBody.stop('20261012-170448-5b71'));
      failPut = true;
      final first = await relay.resend(pending).toList();
      expect(first.single, isA<RelayNotSent>());
      expect((first.single as RelayNotSent).text, offlineText);
      failPut = false;
      final statuses = <RelayStatus>[];
      final done = relay.resend(pending).listen(statuses.add).asFuture<void>();
      await pump();
      feed(
        pending.rid,
        const RtdbPut('/', {
          'result': {
            'ok': false,
            'at': 1,
            'code': 'not_live',
            'error': 'session is not live',
            'retry': false,
          },
        }),
      );
      await done;
      expect(puts.single.url.path, contains(pending.rid));
      final failed = statuses.single as RelayFailed;
      expect(failed.code, 'not_live');
      expect(
        failed.text,
        'That session is no longer live. session is not live',
      );
      expect(failed.retry, isFalse);
    },
  );

  test('send mints a fresh rid; a malformed result fails loudly', () async {
    final statuses = <RelayStatus>[];
    final done = relay
        .send(RequestBody.subjectNew('cars'))
        .listen(statuses.add)
        .asFuture<void>();
    await pump();
    final rid = puts.single.url.pathSegments[3];
    feed(rid, const RtdbPut('/result', {'ok': 1}));
    await done;
    expect(
      (statuses.single as RelayFailed).text,
      startsWith('Unreadable reply'),
    );
  });

  test('statusOf on an empty node is queued; default clock', () {
    expect(statusOf(null), isA<RelayQueued>());
    final wall = RequestRelay(
      client: relay.client,
      stream: stream,
      dev: _dev,
      ulid: UlidGenerator(),
    ).prepare(RequestBody.stop('20261012-170448-5b71'));
    expect(wall.req.sentAt, greaterThan(1700000000000));
  });

  test('error texts', () {
    expect(errorText('daily_new_cap', null), contains('limit of new cards'));
    // A blocking code never repeats the worker's text after the headline.
    expect(errorText('locked', 'card x locked'), isNot(contains('card x')));
    expect(errorText('weird', '  '), 'The request failed (weird).');
    expect(headlineFor(null), 'The request failed.');
    expect(pcOfflineText, startsWith('PC offline'));
  });
}
