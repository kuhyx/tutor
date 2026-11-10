import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/editor_screen.dart';
import 'package:tutor/ui/focus_screen.dart';
import 'package:tutor/ui/history_screen.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/plan_screen.dart';
import 'package:tutor/ui/progress_screen.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/services.dart';
import '../support/ui.dart';

void main() {
  testWidgets('counters, subjects, pick, new subject -> plan', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    var signedOut = false;
    await pumpScreen(
      t,
      HomeScreen(services: s, onSignedOut: () => signedOut = true),
    );
    expect(find.text('23/60'), findsOneWidget); // credited / target
    expect(glyphsLabelled('Continue session'), findsOneWidget);
    expect(find.text('1/4'), findsOneWidget); // modules reviewed

    await t.tap(find.text('Vegetable gardening'));
    await t.pumpAndSettle();
    expect(find.byType(PlanScreen), findsOneWidget); // draft -> Plan screen
    await t.pageBack();
    await t.pumpAndSettle();

    db.root = setAt(db.root, 'tutor/v1/subjects/garden/meta/status', 'active');
    db.root = setAt(db.root, 'tutor/v1/rev/catalog', 8);
    await t.tap(glyphsLabelled('Refresh'));
    await t.pumpAndSettle();
    await t.tap(glyphsLabelled('Learn this next'));
    await t.pumpAndSettle();
    expect(getAt(db.root, 'tutor/v1/prefs/current_subject'), 'garden');

    await t.enterText(find.byType(TextField), 'how bridges stand');
    await t.tap(glyphsLabelled('Draft a plan'));
    await sent(t);
    expect(cueOfKind(CueKind.pending), findsOneWidget);
    final req = await answer(t, db, stream, data: {'subject': 'garden'});
    expect(req['kind'], 'subject_new');
    expect(find.byType(PlanScreen), findsOneWidget);
    await t.pageBack();
    await t.pumpAndSettle();

    await t.tap(find.byIcon(Icons.more_vert));
    await t.pumpAndSettle();
    await t.tap(bySpoken('Sign out').first);
    await t.pumpAndSettle();
    expect(signedOut, isTrue);
  });

  testWidgets('completed subject: go deeper / review only; failed: retry', (
    t,
  ) async {
    final db = fixtureDb();
    db.root = setAt(db.root, 'tutor/v1/subjects/car/meta/status', 'completed');
    db.root = setAt(db.root, 'tutor/v1/subjects/garden/meta', {
      'title': 'Vegetable gardening',
      'goal': 'grow vegetables',
      'status': 'failed',
      'error': 'no sources found',
      'created': 1,
      'rev': 2,
      'origin': 'generated',
    });
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, HomeScreen(services: s, onSignedOut: () {}));
    // The failure's reason is the status glyph's spoken label only.
    expect(bySpoken('failed · no sources found'), findsOneWidget);
    expect(find.textContaining('no sources found'), findsNothing);
    await t.tap(glyphsLabelled('Review only'));
    await sent(t);
    expect((await answer(t, db, stream))['kind'], 'subject_finish');
    await t.tap(glyphsLabelled('Try again'));
    await sent(t);
    final req = await answer(t, db, stream, code: 'model_error');
    expect(req['body'], {'text': 'grow vegetables'});
    expect(cueOfKind(CueKind.error), findsOneWidget);
  });

  testWidgets('desktop build: no Sign out', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      HomeScreen(services: s, onSignedOut: () {}, allowSignOut: false),
    );
    await t.tap(find.byIcon(Icons.more_vert));
    await t.pumpAndSettle();
    expect(bySpoken('History'), findsOneWidget);
    expect(bySpoken('Sign out'), findsNothing);
  });

  testWidgets('the focus deep link opens the focus screen with autoStart', (
    t,
  ) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      HomeScreen(
        services: s,
        onSignedOut: () {},
        initialRoute: '/focus?start=1',
      ),
      settle: false,
    );
    await t.pump(const Duration(milliseconds: 200));
    final focus = t.widget<FocusScreen>(find.byType(FocusScreen));
    expect(focus.autoStart, isTrue);
  });

  testWidgets('a check-in due on open shows the focus screen', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final kv = MemoryKv();
    final last = DateTime.now().millisecondsSinceEpoch - 450000;
    await kv.set(
      'focus.timer',
      jsonEncode({'running': true, 'last': last, 'counted': 0}),
    );
    final s = services(db, stream, kv: kv);
    await pumpScreen(
      t,
      HomeScreen(services: s, onSignedOut: () {}),
      settle: false,
    );
    await t.pump(const Duration(milliseconds: 200));
    expect(find.byType(FocusScreen), findsOneWidget);
    s.focus.dispose();
    await t.pumpWidget(const SizedBox());
  });

  testWidgets('the plain focus route does not start the timer', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      HomeScreen(services: s, onSignedOut: () {}, initialRoute: '/focus'),
      settle: false,
    );
    await t.pump(const Duration(milliseconds: 200));
    expect(t.widget<FocusScreen>(find.byType(FocusScreen)).autoStart, isFalse);
  });

  testWidgets('menu routes and the initial route', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      HomeScreen(services: s, onSignedOut: () {}, initialRoute: '/progress'),
    );
    expect(find.byType(ProgressScreen), findsOneWidget);
    await t.pageBack();
    await t.pumpAndSettle();
    for (final (item, screen) in [
      ('History', HistoryScreen),
      ('Edit cards', EditorScreen),
    ]) {
      await t.tap(find.byIcon(Icons.more_vert));
      await t.pumpAndSettle();
      await t.tap(bySpoken(item).first);
      await t.pumpAndSettle();
      expect(find.byType(screen), findsOneWidget);
      await t.pageBack();
      await t.pumpAndSettle();
    }
    await t.tap(find.byIcon(Icons.more_vert));
    await t.pumpAndSettle();
    await t.tap(bySpoken('Display size').first);
    await t.pumpAndSettle();
    expect(find.text('100%'), findsOneWidget);
    await t.tap(glyphsLabelled('Done'));
    await t.pumpAndSettle();
    await t.tap(find.byIcon(Icons.more_vert));
    await t.pumpAndSettle();
    await t.tap(bySpoken('Report a problem').first);
    await t.pumpAndSettle();
    expect(glyphsLabelled('Save report'), findsOneWidget);
  });
}
