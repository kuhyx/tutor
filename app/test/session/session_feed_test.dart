import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/sync/rtdb_event.dart';

import '../model/samples.dart';
import '../support/fake_stream.dart';

const _sid = '20261012-170448-5b71';
const _sid2 = '20261012-180000-aaaa';
const _base = 'tutor/v1/sessions/$_sid';

Future<void> _tick() => Future<void>.delayed(Duration.zero);

void main() {
  late FakeStream stream;
  late SessionFeed feed;

  setUp(() {
    stream = FakeStream();
    feed = SessionFeed(stream);
  });

  test('live -> follows its session; meta and msgs parse', () async {
    feed
      ..start()
      ..start(); // idempotent
    stream.listens['tutor/v1/live']!
      ..add(const RtdbConnected())
      ..add(const RtdbPut('/', {'session': _sid, 'subject': 'automation'}));
    await _tick();
    expect(feed.loaded.value, isTrue);
    expect(feed.live.value!.session, _sid);
    expect(feed.view.value!.sid, _sid);
    expect(feed.view.value!.last, isNull);
    stream.listens['$_base/meta']!.add(const RtdbPut('/', sessionMeta));
    stream.listens['$_base/msgs']!
      ..add(const RtdbPut('/', {'m0002': learnerMessage, 'x': 1}))
      ..add(const RtdbPatch('/', {'m0001': tutorMessage, 'm0003': 5}));
    await _tick();
    final view = feed.view.value!;
    expect(view.meta!.n, 14);
    expect(view.messages.map((m) => m.key), ['m0001', 'm0002']);
    expect(view.last!.message.role, 'learner');
    // Same session again: no resubscribe.
    final meta = stream.listens['$_base/meta'];
    feed.follow(_sid);
    expect(stream.listens['$_base/meta'], same(meta));
    await feed.dispose();
  });

  test('live null keeps the stopped session; malformed live is null', () async {
    feed
      ..follow(_sid)
      ..start();
    final live = stream.listens['tutor/v1/live']!
      ..add(const RtdbPut('/', null))
      ..add(const RtdbKeepAlive());
    await _tick();
    expect(feed.live.value, isNull);
    expect(feed.view.value!.sid, _sid);
    live.add(const RtdbPut('/', {'subject': 'x'}));
    await _tick();
    expect(feed.live.value, isNull);
    live.add(const RtdbPut('/', {'session': 'not-a-sid'}));
    await _tick();
    expect(feed.view.value!.sid, _sid);
    live.add(const RtdbPut('/', {'session': _sid2}));
    await _tick();
    expect(feed.view.value!.sid, _sid2);
    await feed.dispose();
  });

  test(
    'stop keeps the view; start re-follows it from a fresh snapshot',
    () async {
      feed.follow(_sid);
      await feed.stop();
      expect(feed.view.value!.sid, _sid);
      stream.listens.clear();
      feed.start();
      expect(stream.listens.keys, contains('$_base/meta'));
      await feed.dispose();
    },
  );

  test('parsers tolerate junk', () {
    expect(parseMessages(null), isEmpty);
    expect(parseMeta('x'), isNull);
    expect(parseMeta(<String, dynamic>{'subject': 1}), isNull);
  });
}
