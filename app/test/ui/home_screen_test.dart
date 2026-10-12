import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/home_screen.dart';

import '../support/fake_stream.dart';
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
      size: const Size(412, 1400),
    );
    expect(find.textContaining('Credited 23/60 min'), findsOneWidget);
    expect(find.text('Continue session'), findsOneWidget);
    expect(find.textContaining('1/4 modules mastered'), findsOneWidget);

    await t.tap(find.text('Vegetable gardening'));
    await t.pumpAndSettle();
    expect(find.text('Plan'), findsWidgets); // draft -> Plan screen
    await t.pageBack();
    await t.pumpAndSettle();

    db.root = setAt(db.root, 'tutor/v1/subjects/garden/meta/status', 'active');
    db.root = setAt(db.root, 'tutor/v1/rev/catalog', 8);
    await t.tap(find.byTooltip('Refresh'));
    await t.pumpAndSettle();
    await t.tap(find.text('Learn this next'));
    await t.pumpAndSettle();
    expect(getAt(db.root, 'tutor/v1/prefs/current_subject'), 'garden');

    await t.enterText(find.byType(TextField), 'how bridges stand');
    await t.tap(find.text('Draft a plan'));
    await sent(t);
    expect(find.textContaining('drafts a plan'), findsOneWidget);
    final req = await answer(t, db, stream, data: {'subject': 'garden'});
    expect(req['kind'], 'subject_new');
    expect(find.text('Modules (teaching order)'), findsOneWidget);
    await t.pageBack();
    await t.pumpAndSettle();

    await t.tap(find.byTooltip('More'));
    await t.pumpAndSettle();
    await t.tap(find.text('Sign out'));
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
    expect(find.textContaining('no sources found'), findsOneWidget);
    await t.tap(find.text('Review only'));
    await sent(t);
    expect((await answer(t, db, stream))['kind'], 'subject_finish');
    await t.tap(find.text('Try again'));
    await sent(t);
    final req = await answer(t, db, stream, code: 'model_error');
    expect(req['body'], {'text': 'grow vegetables'});
    expect(find.textContaining('failed on this turn'), findsOneWidget);
  });

  testWidgets('desktop build: no Sign out', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      HomeScreen(services: s, onSignedOut: () {}, allowSignOut: false),
    );
    await t.tap(find.byTooltip('More'));
    await t.pumpAndSettle();
    expect(find.text('History'), findsOneWidget);
    expect(find.text('Sign out'), findsNothing);
  });

  testWidgets('menu routes and the initial route', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      HomeScreen(services: s, onSignedOut: () {}, initialRoute: '/progress'),
    );
    expect(find.text('Credited minutes per day'), findsOneWidget);
    await t.pageBack();
    await t.pumpAndSettle();
    for (final (item, title) in [
      ('History', 'History'),
      ('Edit cards', 'Edit cards'),
    ]) {
      await t.tap(find.byTooltip('More'));
      await t.pumpAndSettle();
      await t.tap(find.text(item));
      await t.pumpAndSettle();
      expect(find.widgetWithText(AppBar, title), findsOneWidget);
      await t.pageBack();
      await t.pumpAndSettle();
    }
    await t.tap(find.byTooltip('More'));
    await t.pumpAndSettle();
    await t.tap(find.text('Report a problem'));
    await t.pumpAndSettle();
    expect(find.text('Save report'), findsOneWidget);
  });
}
