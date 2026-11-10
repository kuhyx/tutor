import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/editor_screen.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/plan_screen.dart';
import 'package:tutor/ui/report_dialog.dart';
import 'package:tutor/ui/review_screen.dart';
import 'package:tutor/ui/transcript_screen.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../support/fake_stream.dart';
import '../support/label_finders.dart';
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
    // About one message: its glyph and its (shortened) text.
    expect(find.byIcon(Icons.chat_bubble_outline), findsOneWidget);
    expect(find.textContaining('xxx'), findsOneWidget);
    await t.tap(glyphsLabelled('Save report'));
    await t.pumpAndSettle();
    expect(cueOfKind(CueKind.error), findsOneWidget); // empty: kept
    ChoiceChip chip(String c) =>
        t.widget<ChoiceChip>(find.byKey(ValueKey('report-$c')));
    expect(chip('response').selected, isTrue); // about a message
    await t.tap(find.byKey(const ValueKey('report-experience')));
    await t.pumpAndSettle();
    expect(chip('experience').selected, isTrue);
    expect(chip('response').selected, isFalse);
    await t.tap(find.byKey(const ValueKey('report-ui')));
    await t.pumpAndSettle();
    await t.enterText(find.byType(TextField), 'same image twice');
    db.offline = true;
    await t.tap(glyphsLabelled('Save report'));
    await t.pumpAndSettle();
    expect(find.text('same image twice'), findsOneWidget);
    expect(cueOfKind(CueKind.error), findsOneWidget);
    db.offline = false;
    await t.tap(glyphsLabelled('Save report'));
    await t.pumpAndSettle();
    expect(cueOfKind(CueKind.ok), findsOneWidget); // saved
    final fb = getAt(db.root, 'tutor/v1/feedback')! as Map;
    final report = fb.values.single as Map;
    expect(report['category'], 'ui');
    expect(report['msg'], 'm0004');
    await t.tap(glyphsLabelled('Close'));
    await t.pumpAndSettle();
    expect(cueOfKind(CueKind.ok), findsNothing);
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
    for (final (route, screen) in [
      ('/plan/garden', PlanScreen),
      ('/history/20261011-090000-a1b2', TranscriptScreen),
      ('/review', ReviewScreen),
      ('/editor', EditorScreen),
      ('/report', ReportDialog),
    ]) {
      final opened = openRoute(ctx, s, route);
      await t.pumpAndSettle();
      expect(find.byType(screen), findsOneWidget, reason: route);
      Navigator.of(ctx).pop();
      await t.pumpAndSettle();
      await opened;
    }
  });
}
