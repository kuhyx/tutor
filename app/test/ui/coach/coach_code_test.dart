import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../coach/coach_fixtures.dart';
import 'coach_support.dart';

void main() {
  late CoachRig rig;
  setUp(() => rig = CoachRig());

  Future<void> codeTab(WidgetTester t) async {
    await t.tap(find.byIcon(Icons.code));
    await t.pumpAndSettle();
  }

  TextEditingController editor(WidgetTester t) =>
      t.widget<TextField>(find.byKey(const ValueKey('sql-editor'))).controller!;

  Future<void> pick(WidgetTester t, String name) async {
    await t.tap(find.byKey(const ValueKey('lang')));
    await t.pumpAndSettle();
    await t.tap(find.text(name).last);
    await t.pumpAndSettle();
  }

  testWidgets('starter code is prefilled, line numbers and symbols show', (
    t,
  ) async {
    await rig.open(t);
    await codeTab(t);
    expect(editor(t).text, startsWith('class Solution'));
    expect(find.byKey(const ValueKey('gutter')), findsOneWidget);
    expect(find.byKey(const ValueKey('key-{')), findsOneWidget);
    expect(find.byKey(const ValueKey('key-  ')), findsOneWidget);
    expect(find.text('Python 3'), findsOneWidget);
  });

  testWidgets('no symbol row on a desktop window', (t) async {
    await rig.open(t, size: const Size(1366, 900));
    await t.tap(find.byIcon(Icons.code));
    await t.pumpAndSettle();
    expect(find.byKey(const ValueKey('key-{')), findsNothing);
    expect(find.byKey(const ValueKey('statement-pane')), findsOneWidget);
    expect(find.byKey(const ValueKey('statement-header')), findsNothing);
  });

  testWidgets('each language keeps its own code', (t) async {
    await rig.open(t);
    await codeTab(t);
    await t.enterText(find.byKey(const ValueKey('sql-editor')), 'x = 1');
    await pick(t, 'JavaScript');
    expect(editor(t).text, startsWith('var twoSum'));
    await pick(t, 'Python 3');
    expect(editor(t).text, 'x = 1');
    await pick(t, 'TypeScript');
    expect(editor(t).text, isEmpty);
  });

  testWidgets('a saved language and draft come back on the next open', (
    t,
  ) async {
    await rig.open(t);
    await codeTab(t);
    await pick(t, 'JavaScript');
    await t.enterText(find.byKey(const ValueKey('sql-editor')), 'let a;');
    await rig.open(t);
    await codeTab(t);
    expect(editor(t).text, 'let a;');
    expect(find.text('JavaScript'), findsOneWidget);
  });

  testWidgets('a SQL problem offers its dialects and SQL symbols', (t) async {
    await rig.open(t, first: sqlOpenData);
    await codeTab(t);
    expect(find.text('MySQL'), findsOneWidget);
    expect(editor(t).text, startsWith('# Write your MySQL'));
    expect(find.byKey(const ValueKey("key-'")), findsOneWidget);
    await t.tap(find.byKey(const ValueKey('lang')));
    await t.pumpAndSettle();
    expect(find.text('PostgreSQL'), findsOneWidget);
  });

  testWidgets('Run sends the code; examples show got against expected', (
    t,
  ) async {
    await rig.open(t);
    await codeTab(t);
    await t.enterText(find.byKey(const ValueKey('sql-editor')), 'print(1)');
    await t.pump();
    await rig.tap(t, 'run');
    expect(rig.kind(), 'lc_run');
    expect(rig.body(), {'lc_id': lcId, 'lang': 'python3', 'code': 'print(1)'});
    await rig.reply(t, runData);
    expect(find.text('1/3'), findsOneWidget);
    expect(find.text('[1,2]'), findsOneWidget);
    expect(find.text('[0,2]'), findsOneWidget);
    expect(find.text('TypeError'), findsOneWidget);
    expect(find.text('#3'), findsOneWidget);
  });

  testWidgets('SQL examples show both tables, the cell that differs marked', (
    t,
  ) async {
    await rig.open(t, first: sqlOpenData);
    await codeTab(t);
    await t.enterText(find.byKey(const ValueKey('sql-editor')), 'SELECT 1');
    await t.pump();
    await rig.tap(t, 'run');
    expect(rig.body()['lang'], 'mysql');
    await rig.reply(t, sqlRunData);
    await t.ensureVisible(find.byKey(const ValueKey('mark-1-1')));
    expect(find.byKey(const ValueKey('mark-1-1')), findsOneWidget);
    expect(find.text('NULL'), findsOneWidget);
    expect(find.text('Jan'), findsOneWidget);
  });

  testWidgets('a run-level error, no examples, and a held run', (t) async {
    await rig.open(t);
    await codeTab(t);
    await t.enterText(find.byKey(const ValueKey('sql-editor')), 'x');
    await t.pump();
    await rig.tap(t, 'run');
    await rig.reply(t, {'error': 'timeout', 'no_examples': true});
    expect(find.text('timeout'), findsOneWidget);
    expect(find.byIcon(Icons.help_outline), findsOneWidget);
    await rig.tap(t, 'run');
    await rig.reply(t, {'held': true, 'note': 'Open the gate first'});
    expect(find.byKey(const ValueKey('run-note')), findsOneWidget);
    expect(find.text('timeout'), findsNothing);
  });

  testWidgets('an unparsable result shows the problem in the chat tab', (
    t,
  ) async {
    await rig.open(t);
    await codeTab(t);
    await t.enterText(find.byKey(const ValueKey('sql-editor')), 'x');
    await t.pump();
    await rig.tap(t, 'run');
    await rig.reply(t, {'examples': 3});
    await t.tap(find.byIcon(Icons.forum_outlined));
    await t.pumpAndSettle();
    expect(find.textContaining('expected array'), findsOneWidget);
  });

  testWidgets('with the phone keyboard up Run stays reachable', (t) async {
    await rig.open(t);
    pixel(t, keyboard: 300);
    await codeTab(t);
    await t.enterText(find.byKey(const ValueKey('sql-editor')), 'a\nb\nc');
    await t.pump();
    await t.ensureVisible(find.byKey(const ValueKey('run')));
    final run = t.getRect(find.byKey(const ValueKey('run')));
    final screenH = t.view.physicalSize.height / t.view.devicePixelRatio;
    expect(run.bottom, lessThanOrEqualTo(screenH - 300 / 2.625));
    expect(find.byKey(const ValueKey('run')).hitTestable(), findsOneWidget);
  });
}
