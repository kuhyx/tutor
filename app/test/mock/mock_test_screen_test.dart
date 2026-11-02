import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/sql/data_grid.dart';
import 'package:tutor/widgets/code_symbol_bar.dart';

import '../support/ui.dart';
import 'mock_fixtures.dart';
import 'mock_support.dart';

void main() {
  late Rig rig;
  setUp(() => rig = Rig());

  Finder key(String k) => find.byKey(ValueKey(k));

  testWidgets('shows the clock, chips and the first question', (t) async {
    await rig.pumpTest(t);
    expect(find.text('59:00'), findsOneWidget);
    expect(find.text('M1'), findsOneWidget);
    expect(find.text('M2'), findsOneWidget);
    expect(find.text('PY'), findsOneWidget);
    expect(find.text('S1'), findsOneWidget);
    expect(find.text('print([1, 2][::-1])'), findsOneWidget);
    expect(find.textContaining('seed bank'), findsOneWidget);
    await t.tap(key('notes-close'));
    await t.pump();
    expect(find.textContaining('seed bank'), findsNothing);
  });

  testWidgets('picking an option submits it and marks the chip', (t) async {
    final m = await rig.pumpTest(t);
    await t.tap(key('opt-1'));
    await t.pumpAndSettle();
    expect(m.answers['q1'], '1');
    expect(m.isSubmitted('q1'), isTrue);
    expect(find.byIcon(Icons.check_circle), findsOneWidget);
    final sent = mockBodies(rig.db).single;
    expect((sent['op'], sent['task'], sent['answer']), ('answer', 'q1', '1'));
    expect(rig.kv.data['mock.active'], contains('"q1":"1"'));
    await t.tap(key('nav-1'));
    await t.pump();
    expect(find.text('print(len({}))'), findsOneWidget);
  });

  testWidgets('a picked answer can change before the end', (t) async {
    final m = await rig.pumpTest(t);
    await t.tap(key('opt-1'));
    await t.pumpAndSettle();
    await t.tap(key('opt-0'));
    await t.pumpAndSettle();
    expect(m.answers['q1'], '0');
    expect(mockBodies(rig.db).map((b) => b['answer']), ['1', '0']);
  });

  testWidgets('SQL: symbols type, Run shows output, Submit queues', (t) async {
    final m = await rig.pumpTest(t);
    await t.tap(key('nav-3'));
    await t.pump();
    expect(find.byType(CodeSymbolBar), findsOneWidget);
    expect(find.text('Ann'), findsWidgets);
    await t.enterText(find.byType(EditableText), 'select');
    await t.tap(key('key-('));
    await t.pump();
    expect(m.answers['s1'], 'select(');
    await t.tap(key('run'));
    await t.pump(const Duration(milliseconds: 50));
    final run = mockBodies(rig.db).last;
    expect((run['op'], run['task'], run['answer']), ('run', 's1', 'select('));
    await answer(
      t,
      rig.db,
      rig.stream,
      data: {
        'ok': true,
        'columns': ['name'],
        'rows': [
          ['Bob'],
        ],
      },
    );
    expect(find.text('Bob'), findsOneWidget);
    expect(find.byType(DataGridView), findsWidgets);
    await t.ensureVisible(key('submit'));
    await t.tap(key('submit'));
    await t.pumpAndSettle();
    expect(mockBodies(rig.db).last['answer'], 'select(');
    expect(m.isSubmitted('s1'), isTrue);
  });

  testWidgets('a failed Run shows the database error', (t) async {
    await rig.pumpTest(t);
    await t.tap(key('nav-3'));
    await t.pump();
    await t.enterText(find.byType(EditableText), 'selec');
    await t.tap(key('run'));
    await t.pump(const Duration(milliseconds: 50));
    await answer(
      t,
      rig.db,
      rig.stream,
      data: {'ok': false, 'error': 'You have an error'},
    );
    expect(find.text('You have an error'), findsOneWidget);
  });

  testWidgets('Python Run shows per-example verdicts; starter prefilled', (
    t,
  ) async {
    await rig.pumpTest(t);
    await t.tap(key('nav-2'));
    await t.pump();
    expect(find.textContaining('def f(s)'), findsWidgets);
    await t.tap(key('run'));
    await t.pump(const Duration(milliseconds: 50));
    await answer(
      t,
      rig.db,
      rig.stream,
      data: {
        'examples': [
          {'n': 1, 'ok': true, 'input': 'a', 'expected': 'a', 'actual': 'a'},
          {'n': 2, 'ok': false, 'input': 'b', 'expected': 'b', 'actual': 'c'},
        ],
      },
    );
    expect(key('example-1-ok'), findsOneWidget);
    expect(key('example-2-bad'), findsOneWidget);
  });

  testWidgets('the symbol bar stays above the keyboard', (t) async {
    await rig.pumpTest(t);
    await t.tap(key('nav-3'));
    await t.pump();
    t.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(t.view.resetViewInsets);
    await t.pump();
    final bar = t.getBottomLeft(find.byType(CodeSymbolBar)).dy;
    expect(bar, lessThanOrEqualTo(915 - 300));
    expect(t.takeException(), isNull);
  });
}
