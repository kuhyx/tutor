import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/drill/anki_sync.dart';
import 'package:tutor/ui/review_screen.dart';

import '../support/drill.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/ui.dart';

const _sync = 'Sync Anki & credit';

// Opens the drill (first question answered) over an [AnkiSync] on [launcher];
// [now] is its clock.
Future<(FakeRtdb, FakeStream)> _open(
  WidgetTester t,
  AnkiLauncher launcher, {
  DateTime Function()? now,
}) async {
  final db = fixtureDb();
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  await pumpScreen(
    t,
    ReviewScreen(
      services: s,
      drill: true,
      anki: AnkiSync(relay: s.relay, launcher: launcher, now: now),
    ),
    size: const Size(412, 915),
    settle: false,
  );
  await answer(t, db, stream, data: drillQuestion());
  return (db, stream);
}

Future<void> _tick(WidgetTester t) async {
  await t.pump(const Duration(seconds: 1));
  await sent(t);
}

void main() {
  testWidgets('polls anki_status each second until the credit rises', (
    t,
  ) async {
    final launcher = FakeLauncher();
    final (db, stream) = await _open(t, launcher);
    await t.tap(find.text(_sync));
    await sent(t);
    // The baseline comes first, so a fast sync cannot be missed.
    expect(lastRequest(db).$2['kind'], 'anki_status');
    await answer(t, db, stream, data: ankiStatus(5), settle: false);
    await sent(t);
    expect(launcher.launches, 1);
    expect(find.text('Syncing AnkiDroid...'), findsOne);
    // Not yet: the same 5, so it polls again a second later.
    await _tick(t);
    await answer(t, db, stream, data: ankiStatus(5), settle: false);
    await _tick(t);
    await answer(
      t,
      db,
      stream,
      data: {
        ...ankiStatus(8),
        'unavailable': {'until': 1792000000, 'reason': 'limit'},
      },
    );
    expect(find.text('+3 min from Anki'), findsOne);
    // The PC's Claude-out marker reaches the banner.
    expect(find.textContaining('Claude limit'), findsOne);
    expect(find.text(_sync), findsOne);
  });

  testWidgets('gives up after the timeout, tolerating a bad poll', (t) async {
    final clock = DateTime(2026, 10, 15, 12);
    var calls = 0;
    final (db, stream) = await _open(
      t,
      FakeLauncher(),
      // The deadline is +60 s; the checks read +30 s, then +60 s: one poll.
      now: () => clock.add(Duration(seconds: 30 * calls++)),
    );
    await t.tap(find.text(_sync));
    await sent(t);
    await answer(t, db, stream, data: ankiStatus(5), settle: false);
    await _tick(t);
    await answer(t, db, stream, data: {'credited_today_min': 'x'});
    expect(find.textContaining('No new credit from Anki yet'), findsOne);
  });

  testWidgets('a failed baseline ends the wait', (t) async {
    final (db, stream) = await _open(t, FakeLauncher());
    await t.tap(find.text(_sync));
    await sent(t);
    await answer(t, db, stream, code: 'worker_error');
    expect(find.text('The PC did not answer.'), findsOne);
  });

  testWidgets('without AnkiDroid it says so', (t) async {
    final missing = FakeLauncher(ok: false);
    final (db, stream) = await _open(t, missing);
    await t.tap(find.text(_sync));
    await sent(t);
    await answer(t, db, stream, data: ankiStatus(1));
    expect(find.textContaining('did not start a sync'), findsOne);
    expect(missing.launches, 1);
  });

  testWidgets('the button is hidden where the intent cannot run', (t) async {
    await _open(t, FakeLauncher(supported: false));
    expect(find.text(_sync), findsNothing);
  });

  group('ChannelAnkiLauncher', () {
    const channel = MethodChannel('com.kuhy.tutor/anki');
    final messenger =
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    tearDown(() => messenger.setMockMethodCallHandler(channel, null));

    test('sync: true, null and a platform error', () async {
      final launcher = ChannelAnkiLauncher();
      final answers = <Object? Function()>[
        () => true,
        () => null,
        () => throw PlatformException(code: 'x'),
      ];
      messenger.setMockMethodCallHandler(channel, (call) async {
        expect(call.method, 'sync');
        return answers.removeAt(0)();
      });
      expect(await launcher.sync(), isTrue);
      expect(await launcher.sync(), isFalse);
      expect(await launcher.sync(), isFalse);
    });

    test('supported: Android only, never the web build', () {
      expect(ChannelAnkiLauncher(platform: _no).supported, isFalse);
      expect(ChannelAnkiLauncher(platform: _yes).supported, isTrue);
      // flutter_test runs as Android, off the web.
      expect(defaultTargetPlatform, TargetPlatform.android);
      expect(ChannelAnkiLauncher().supported, isTrue);
    });
  });
}

bool _no() => false;
bool _yes() => true;
