import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/plan_screen.dart';

import '../support/fake_stream.dart';
import '../support/ui.dart';

void main() {
  testWidgets('draft: reorder, edit, add, remove, save, approve, revise', (
    t,
  ) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      PlanScreen(services: s, subject: 'garden'),
      size: const Size(1000, 2400),
    );
    expect(find.text('1. Light and orientation'), findsOneWidget);
    // Approve only while nothing is unsaved.
    await t.tap(find.byTooltip('Move down').first);
    await t.pumpAndSettle();
    expect(find.text('1. Soil and containers'), findsOneWidget);
    expect(
      t
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Approve plan'),
          )
          .onPressed,
      isNull,
    );
    await t.tap(find.text('Undo edits'));
    await t.pumpAndSettle();
    for (var i = 0; i < 3; i++) {
      await t.tap(find.byTooltip('Move down').at(i));
      await t.pumpAndSettle();
    }
    expect(find.textContaining('not before it'), findsOneWidget);
    await t.tap(find.text('Undo edits'));
    await t.pumpAndSettle();

    await t.tap(find.byTooltip('Edit').at(1));
    await t.pumpAndSettle();
    await t.enterText(find.widgetWithText(TextField, 'Title'), 'Soil');
    await t.tap(find.widgetWithText(CheckboxListTile, 'Light and orientation'));
    await t.pumpAndSettle();
    await t.tap(find.text('Done'));
    await t.pumpAndSettle();
    expect(find.text('2. Soil'), findsOneWidget);
    await t.tap(find.byTooltip('Edit').at(1));
    await t.pumpAndSettle();
    await t.tap(find.widgetWithText(CheckboxListTile, 'Light and orientation'));
    await t.tap(find.text('Cancel'));
    await t.pumpAndSettle();

    await t.enterText(
      find.widgetWithText(TextField, 'Add a module (title)'),
      'Pests',
    );
    await t.tap(find.byTooltip('Add module'));
    await t.pumpAndSettle();
    await t.tap(find.byTooltip('Remove').last);
    await t.pumpAndSettle();
    await t.tap(find.text('Save edits'));
    await sent(t);
    final edit = await answer(t, db, stream, data: {'plan_rev': 2});
    expect(edit['kind'], 'plan_edit');
    final modules = (edit['body'] as Map)['modules'] as List;
    expect((modules[1] as Map)['title'], 'Soil');
    expect((modules[1] as Map)['requires'], ['light']);

    await t.enterText(
      find.widgetWithText(
        TextField,
        'Comment (e.g. "less history, more maintenance")',
      ),
      'less soil',
    );
    await t.tap(find.text('Redraft with this comment'));
    await sent(t);
    expect((await answer(t, db, stream))['kind'], 'plan_revise');
    await t.tap(find.text('Approve plan'));
    await sent(t);
    expect(
      (await answer(t, db, stream, code: 'plan_conflict'))['kind'],
      'plan_approve',
    );
  });

  testWidgets('approved: status and recall; failed module retries', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, PlanScreen(services: s, subject: 'car'));
    expect(find.textContaining('recall 85%'), findsOneWidget);
    await t.tap(find.text('Retry'));
    await sent(t);
    expect((await answer(t, db, stream))['kind'], 'plan_approve');
  });

  testWidgets('drafting, failed, missing and unreachable', (t) async {
    final db = fixtureDb();
    db.root = setAt(
      db.root,
      'tutor/v1/subjects/garden/meta/status',
      'drafting',
    );
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, PlanScreen(services: s, subject: 'garden'));
    expect(find.text('The tutor is drafting the plan'), findsOneWidget);
    db.root = setAt(db.root, 'tutor/v1/subjects/garden/meta/status', 'failed');
    db.root = setAt(
      db.root,
      'tutor/v1/subjects/garden/meta/error',
      'no sources',
    );
    await t.tap(find.byTooltip('Reload'));
    await t.pumpAndSettle();
    expect(find.text('no sources'), findsOneWidget);
    await pumpScreen(
      t,
      PlanScreen(services: s, subject: 'nope', key: UniqueKey()),
    );
    expect(find.textContaining('does not exist'), findsOneWidget);
    db.offline = true;
    await pumpScreen(
      t,
      PlanScreen(services: s, subject: 'car', key: UniqueKey()),
    );
    expect(find.textContaining('Could not load'), findsOneWidget);
  });
}
