// Home during a Claude outage (plan e79be0be-0 steps 2 and 7, mockup F1):
// the red banner with the reason glyph, the reset ring and the free-chat
// glyph; Start runs the chooser before any chat request goes out.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/model/codes.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/model/outage_window.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/drill_view.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/outage_banner.dart';
import 'package:tutor/ui/read_screen.dart';
import 'package:tutor/ui/review_screen.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../support/drill.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/read.dart';
import '../support/ui.dart';

int _nowS() => DateTime.now().millisecondsSinceEpoch ~/ 1000;

/// Home with `stats.today.unavailable` until [until] (null: no outage);
/// [live] keeps the fixture's live session (else Start is "Continue
/// learning" on the current subject).
Future<(FakeRtdb, FakeStream, TutorServices)> _home(
  WidgetTester t, {
  int? until,
  Size size = kPhone,
  bool live = false,
}) async {
  final db = fixtureDb();
  if (!live) db.root = setAt(db.root, 'tutor/v1-e2e/live', null);
  if (until != null) {
    db.root = setAt(db.root, 'tutor/v1-e2e/stats/today/unavailable', {
      'until': until,
      'reason': 'rate_limit',
    });
  }
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  await pumpScreen(
    t,
    HomeScreen(services: s, onSignedOut: () {}),
    size: size,
  );
  return (db, stream, s);
}

Future<void> _start(WidgetTester t) async {
  await t.tap(controlByLabel('Continue learning'));
  await sent(t);
}

Map<String, Object?>? _requests(FakeRtdb db) =>
    getAt(db.root, 'tutor/v1-e2e/requests') as Map<String, Object?>?;

void main() {
  testWidgets('an open outage shows the banner on phone and desktop', (
    t,
  ) async {
    final until = _nowS() + 7200;
    for (final size in [kPhone, const Size(1366, 900)]) {
      await _home(t, until: until, size: size);
      expect(find.byType(OutageBanner), findsOneWidget);
      expect(bySpoken('Claude limit — back at ${hhmm(until)}'), findsOne);
      expect(find.byIcon(Icons.hourglass_bottom), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(controlByLabel('Free chat'), findsOneWidget);
    }
  });

  testWidgets('a past or missing window shows no banner', (t) async {
    await _home(t, until: _nowS() - 60);
    expect(controlByLabel('Free chat'), findsNothing);
    await _home(t);
    expect(controlByLabel('Free chat'), findsNothing);
  });

  testWidgets('the banner leaves by itself once the window ends', (t) async {
    var now = DateTime.fromMillisecondsSinceEpoch(1000 * 1000);
    Widget banner(int until) => OutageBanner(
      OutageWindow(until: until, reason: UnavailableReason.overloaded),
      now: () => now,
      onFreeChat: () {},
    );
    final until = ValueNotifier(1060);
    addTearDown(until.dispose);
    await pumpScreen(
      t,
      Scaffold(
        body: ValueListenableBuilder(
          valueListenable: until,
          builder: (_, at, _) => banner(at),
        ),
      ),
    );
    expect(find.byIcon(Icons.dns_outlined), findsOneWidget);
    // A later window re-arms the timer (the worker extended it).
    until.value = 1120;
    await t.pump();
    now = now.add(const Duration(seconds: 61));
    await t.pump(const Duration(seconds: 61));
    expect(controlByLabel('Free chat'), findsOneWidget);
    now = now.add(const Duration(seconds: 60));
    await t.pump(const Duration(seconds: 60));
    expect(controlByLabel('Free chat'), findsNothing);
  });

  testWidgets('Start with due cards opens Review, no chat request', (t) async {
    final (db, _, s) = await _home(t, until: _nowS() + 7200);
    final month = DateTime.now().millisecondsSinceEpoch - 30 * 86400000;
    await s.events.record(
      TaughtEvent(subject: 'car', card: 'eng-crank', at: month),
    );
    await _start(t);
    await t.pumpAndSettle();
    expect(find.byType(ReviewScreen), findsOneWidget);
    expect(find.byType(DrillView), findsNothing);
    expect(find.byType(SessionScreen), findsNothing);
    expect(_requests(db), isNull);
  });

  testWidgets('Start with nothing due opens read mode for every subject', (
    t,
  ) async {
    final (db, stream, _) = await _home(t, until: _nowS() + 7200);
    await _start(t);
    final probe = await answer(t, db, stream, data: readCard(), settle: false);
    expect(probe['kind'], 'read_next');
    expect(probe['body'], {'subject': null});
    expect(find.byType(ReadScreen), findsOneWidget);
    expect(find.byType(SessionScreen), findsNothing);
  });

  testWidgets('nothing to read, a taught card: Start opens the drill', (
    t,
  ) async {
    final (db, stream, s) = await _home(t, until: _nowS() + 7200);
    await s.events.record(
      TaughtEvent(
        subject: 'car',
        card: 'eng-crank',
        at: DateTime.now().millisecondsSinceEpoch,
      ),
    );
    await _start(t);
    await answer(t, db, stream, data: {'empty': true}, settle: false);
    expect(find.byType(DrillView), findsOneWidget);
    expect(lastRequest(db).$2['kind'], 'drill_next');
  });

  testWidgets('nothing at all: read mode shows its empty glyph', (t) async {
    final (db, stream, _) = await _home(t, until: _nowS() + 7200);
    await _start(t);
    await answer(t, db, stream, data: {'empty': true}, settle: false);
    expect(find.byType(ReadScreen), findsOneWidget);
    await answer(t, db, stream, data: {'empty': true}, settle: false);
    expect(find.byIcon(Icons.inbox_outlined), findsOneWidget);
  });

  testWidgets('a live session still opens during an outage', (t) async {
    final (db, _, _) = await _home(t, until: _nowS() + 7200, live: true);
    await t.tap(controlByLabel('Continue session'));
    await sent(t);
    expect(find.byType(SessionScreen), findsOneWidget);
    expect(find.byType(ReadScreen), findsNothing);
    expect(_requests(db), isNull);
  });

  testWidgets('no outage: Start opens the Session as before', (t) async {
    await _home(t);
    await _start(t);
    expect(find.byType(SessionScreen), findsOneWidget);
  });

  testWidgets('the free-chat glyph starts a free session', (t) async {
    final (db, stream, _) = await _home(t, until: _nowS() + 7200);
    await t.tap(controlByLabel('Free chat'));
    await sent(t);
    expect(find.byType(SessionScreen), findsOneWidget);
    final (_, req) = lastRequest(db);
    expect(req['kind'], 'session_start');
    expect(req['body'], {
      'subject': null,
      'card': null,
      'free': true,
      'device': 'desktop',
    });
    await answer(t, db, stream, code: 'free_unavailable', settle: false);
    expect(find.byIcon(Icons.portable_wifi_off), findsWidgets);
    await t.pageBack();
    await t.pumpAndSettle();
    expect(find.byType(OutageBanner), findsOneWidget);
  });

  testWidgets("read mode's free-chat glyph starts one over read mode", (
    t,
  ) async {
    final (db, stream, _) = await _home(t, until: _nowS() + 7200);
    await _start(t);
    await answer(t, db, stream, data: readCard(), settle: false);
    await answer(t, db, stream, data: readCard(), settle: false);
    // Home's banner glyph stays in the tree under read mode: read mode's own.
    await t.tap(
      find.descendant(
        of: find.byType(ReadScreen),
        matching: controlByLabel('Free chat'),
      ),
    );
    await sent(t);
    expect(lastRequest(db).$2['body'], {
      'subject': null,
      'card': null,
      'free': true,
      'device': 'desktop',
    });
    await answer(t, db, stream, code: 'free_unavailable', settle: false);
    await t.pump(const Duration(seconds: 1)); // the Session's push ends
    expect(find.byIcon(Icons.portable_wifi_off), findsWidgets);
    await t.pageBack();
    await t.pumpAndSettle();
    expect(find.byType(ReadScreen), findsOneWidget);
    expect(find.text('What does the crankshaft do?'), findsOneWidget);
  });
}
