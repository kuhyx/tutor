import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/nav.dart';

import '../support/fake_stream.dart';
import '../support/ui.dart';

void main() {
  testWidgets('about one message: category, text, saved; failures kept', (
    t,
  ) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      Builder(
        builder: (context) => TextButton(
          onPressed: () => showReport(
            context,
            s,
            route: '/session',
            session: '20261012-170448-5b71',
            msg: 'm0004',
            preview: 'x' * 120,
          ),
          child: const Text('open'),
        ),
      ),
    );
    await t.tap(find.text('open'));
    await t.pumpAndSettle();
    expect(find.textContaining('About tutor message m0004'), findsOneWidget);
    await t.tap(find.text('Save report'));
    await t.pumpAndSettle();
    expect(find.textContaining('Your report is kept'), findsOneWidget);
    await t.tap(find.text("Tutor's response"));
    await t.pumpAndSettle();
    await t.tap(find.text('UI').last);
    await t.pumpAndSettle();
    await t.enterText(find.byType(TextField), 'same image twice');
    db.offline = true;
    await t.tap(find.text('Save report'));
    await t.pumpAndSettle();
    expect(find.text('same image twice'), findsOneWidget);
    db.offline = false;
    await t.tap(find.text('Save report'));
    await t.pumpAndSettle();
    expect(find.text('Report saved'), findsOneWidget);
    final fb = getAt(db.root, 'tutor/v1/feedback')! as Map;
    final report = fb.values.single as Map;
    expect(report['category'], 'ui');
    expect(report['msg'], 'm0004');
    await t.tap(find.text('Close'));
    await t.pumpAndSettle();
    expect(find.text('Report saved'), findsNothing);
  });

  testWidgets('route strings open screens; unknown does nothing', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    late BuildContext ctx;
    await pumpScreen(
      t,
      Builder(
        builder: (context) {
          ctx = context;
          return const Text('root');
        },
      ),
    );
    await openRoute(ctx, s, '/nowhere');
    for (final (route, text) in [
      ('/plan/garden', 'Modules (teaching order)'),
      ('/history/20261011-090000-a1b2', 'Past session'),
      ('/review', 'Review'),
      ('/editor', 'Edit cards'),
      ('/report', 'Report a problem'),
    ]) {
      final opened = openRoute(ctx, s, route);
      await t.pumpAndSettle();
      expect(find.text(text), findsWidgets, reason: route);
      Navigator.of(ctx).pop();
      await t.pumpAndSettle();
      await opened;
    }
  });
}
