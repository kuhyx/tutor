import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/plan_screen.dart';
import 'package:tutor/widgets/content_text.dart';

import '../support/fake_stream.dart';
import '../support/learn_finders.dart';
import '../support/ui.dart';

/// The first module's title in the draft editor.
String? _first(WidgetTester t) => t
    .widget<ContentText>(
      find
          .descendant(
            of: find.byType(ListTile).first,
            matching: find.byType(ContentText),
          )
          .first,
    )
    .data;

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
    expect(_first(t), 'Light and orientation');
    // Approve only while nothing is unsaved.
    await t.tap(spoken('Move down').first);
    await t.pumpAndSettle();
    expect(_first(t), 'Soil and containers');
    expect(pressable(t, 'Approve plan'), isFalse);
    await t.tap(spoken('Undo edits'));
    await t.pumpAndSettle();
    for (var i = 0; i < 3; i++) {
      await t.tap(spoken('Move down').at(i));
      await t.pumpAndSettle();
    }
    expect(cueHas('not before it'), findsOneWidget);
    await t.tap(spoken('Undo edits'));
    await t.pumpAndSettle();

    await t.tap(spoken('Edit').at(1));
    await t.pumpAndSettle();
    await t.enterText(fieldLabelled('Title'), 'Soil');
    await t.tap(find.widgetWithText(CheckboxListTile, 'Light and orientation'));
    await t.pumpAndSettle();
    await t.tap(spoken('Done'));
    await t.pumpAndSettle();
    // Renamed; the module that requires it names it too (content).
    expect(moduleTitles(t)[1], 'Soil');
    await t.tap(spoken('Edit').at(1));
    await t.pumpAndSettle();
    await t.tap(find.widgetWithText(CheckboxListTile, 'Light and orientation'));
    await t.tap(spoken('Cancel'));
    await t.pumpAndSettle();

    await t.enterText(fieldLabelled('Add a module (title)'), 'Pests');
    await t.tap(spoken('Add module'));
    await t.pumpAndSettle();
    await t.tap(spoken('Remove').last);
    await t.pumpAndSettle();
    await t.tap(spoken('Save edits'));
    await sent(t);
    final edit = await answer(t, db, stream, data: {'plan_rev': 2});
    expect(edit['kind'], 'plan_edit');
    final modules = (edit['body'] as Map)['modules'] as List;
    expect((modules[1] as Map)['title'], 'Soil');
    expect((modules[1] as Map)['requires'], ['light']);

    await t.enterText(
      fieldLabelled('Comment (e.g. "less history, more maintenance")'),
      'less soil',
    );
    await t.tap(spoken('Redraft with this comment'));
    await sent(t);
    expect((await answer(t, db, stream))['kind'], 'plan_revise');
    await t.tap(spoken('Approve plan'));
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
    expect(spoken('recall 85%'), findsOneWidget);
    await t.tap(spoken('Retry'));
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
    expect(spokenHas('The tutor is drafting the plan'), findsOneWidget);
    db.root = setAt(db.root, 'tutor/v1/subjects/garden/meta/status', 'failed');
    db.root = setAt(
      db.root,
      'tutor/v1/subjects/garden/meta/error',
      'no sources',
    );
    await t.tap(spoken('Reload'));
    await t.pumpAndSettle();
    expect(spokenHas('no sources'), findsOneWidget);
    await pumpScreen(
      t,
      PlanScreen(services: s, subject: 'nope', key: UniqueKey()),
    );
    expect(spokenHas('does not exist'), findsOneWidget);
    db.offline = true;
    await pumpScreen(
      t,
      PlanScreen(services: s, subject: 'car', key: UniqueKey()),
    );
    expect(cueHas('Could not load'), findsOneWidget);
  });
}
