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
    // ONE listen on the session; its events' paths fold into the parts.
    expect(stream.openPaths, ['tutor/v1/live', _base]);
    final session = stream.listens[_base]!
      ..add(const RtdbPut('/meta', sessionMeta))
      ..add(const RtdbPut('/msgs', {'m0002': learnerMessage, 'x': 1}))
      ..add(const RtdbPatch('/msgs', {'m0001': tutorMessage, 'm0003': 5}))
      ..add(const RtdbPut('/receipts/r0001', {'minutes': 1}));
    await _tick();
    final view = feed.view.value!;
    expect(view.meta!.n, 14);
    expect(view.messages.map((m) => m.key), ['m0001', 'm0002']);
    expect(view.last!.message.role, 'learner');
    expect(view.progress, isNull);
    session.add(
      const RtdbPatch('/', {
        'progress': {
          'rid': 'r',
          'steps': {
            's0001': {'kind': 'thinking', 'text': 'hm'},
          },
        },
      }),
    );
    await _tick();
    expect(feed.view.value!.progress!.steps, hasLength(1));
    expect(feed.view.value!.meta!.n, 14);
    // Same session again: no resubscribe.
    feed.follow(_sid);
    expect(stream.listens[_base], same(session));
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
      stream.listens[_base]!.add(
        const RtdbPut('/', {
          'msgs': {'m0001': tutorMessage, 'm0002': learnerMessage},
        }),
      );
      await _tick();
      await feed.stop();
      expect(stream.openPaths, isEmpty);
      expect(feed.view.value!.sid, _sid);
      feed.start();
      expect(stream.openPaths, ['tutor/v1/live', _base]);
      // A reconnect's snapshot is the whole session again.
      stream.listens[_base]!
        ..add(
          const RtdbPut('/', {
            'msgs': {
              'm0001': tutorMessage,
              'm0002': learnerMessage,
              'm0003': learnerMessage,
            },
          }),
        )
        ..add(const RtdbPut('/msgs/m0004', learnerMessage));
      await _tick();
      expect(feed.view.value!.messages.map((m) => m.key), [
        'm0001',
        'm0002',
        'm0003',
        'm0004',
      ]);
      await feed.dispose();
    },
  );

  test('parsers tolerate junk', () {
    expect(parseMessages(null), isEmpty);
    expect(parseMeta('x'), isNull);
    expect(parseMeta(<String, dynamic>{'subject': 1}), isNull);
  });

  test('a subject feed follows only its own subject', () async {
    // kuhy, 2026-10-12: Continue in automation showed the live car session.
    final mine = SessionFeed(stream, subject: 'automation')..start();
    final live = stream.listens['tutor/v1/live']!
      ..add(const RtdbPut('/', {'session': _sid, 'subject': 'car'}));
    await _tick();
    expect(mine.live.value!.subject, 'car');
    expect(mine.view.value, isNull);
    live.add(const RtdbPut('/', {'session': _sid2, 'subject': 'automation'}));
    await _tick();
    expect(mine.view.value!.sid, _sid2);
    await mine.dispose();
  });
}
