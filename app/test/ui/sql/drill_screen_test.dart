import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/ui/sql/drill_screen.dart';
import 'package:tutor/ui/sql/result_view.dart';

import '../../sql/sql_fixtures.dart';
import '../../support/fake_rtdb.dart';
import '../../support/fake_stream.dart';
import '../../support/services.dart';
import '../../support/ui.dart';

void main() {
  late FakeRtdb db;
  late FakeStream stream;
  late MemoryKv kv;

  Future<void> open(
    WidgetTester t, {
    Map<String, Object?> drill = writeDrillData,
  }) async {
    db = FakeRtdb();
    stream = FakeStream();
    await pumpScreen(
      t,
      SqlDrillScreen(
        services: services(db, stream, kv: kv),
        id: 'basics-1',
        title: 'Count rows',
      ),
      settle: false,
    );
    expect(lastRequest(db).$2['kind'], 'sql_get');
    await answer(t, db, stream, data: drill);
  }

  setUp(() => kv = MemoryKv());

  Finder editor() => find.byKey(const ValueKey('sql-editor'));

  Future<void> run(WidgetTester t, String sql) async {
    await t.enterText(editor(), sql);
    await t.pump();
    await t.tap(find.byKey(const ValueKey('run')));
    await t.pump(const Duration(milliseconds: 50));
  }

  testWidgets('shows the task, the tables and an empty editor', (t) async {
    await open(t);
    expect(find.textContaining('employees', findRichText: true), findsWidgets);
    expect(find.text('emp'), findsOneWidget);
    expect(find.text('Ann'), findsOneWidget);
    expect(find.text('NULL'), findsOneWidget);
    expect(editor(), findsOneWidget);
    expect(find.text('SELECT 1;'), findsOneWidget); // the fenced block
  });

  testWidgets('Run needs SQL, sends it, shows marked cells', (t) async {
    await open(t);
    final button = find.byKey(const ValueKey('run'));
    expect(t.widget<FilledButton>(button).onPressed, isNull);
    await run(t, 'select count(*) from emp');
    final (_, req) = lastRequest(db);
    expect(req['kind'], 'sql_run');
    expect(req['body'], {'id': 'basics-1', 'sql': 'select count(*) from emp'});
    await answer(t, db, stream, data: runBadData);
    expect(find.byKey(const ValueKey('mark-0-0')), findsOneWidget);
    expect(find.byKey(const ValueKey('mark-1-0')), findsOneWidget);
    expect(find.byIcon(Icons.cancel_outlined), findsOneWidget);
    expect(find.text('3'), findsOneWidget);
    await t.tap(
      find.descendant(
        of: find.byType(SegmentedButton<bool>),
        matching: find.byIcon(Icons.flag_outlined),
      ),
    );
    await t.pumpAndSettle();
    Finder inResult(String text) =>
        find.descendant(of: find.byType(ResultView), matching: find.text(text));
    expect(inResult('3'), findsNothing);
    expect(inResult('2'), findsOneWidget);
    expect(find.byKey(const ValueKey('mark-0-0')), findsOneWidget);
    expect(find.byKey(const ValueKey('mark-1-0')), findsNothing);
  });

  testWidgets('a match shows the check and no marks', (t) async {
    await open(t);
    await run(t, 'select 2');
    await answer(t, db, stream, data: runGoodData);
    expect(find.byIcon(Icons.check_circle_outline), findsOneWidget);
    expect(find.byType(SegmentedButton<bool>), findsOneWidget);
  });

  testWidgets('an SQL error is shown as text', (t) async {
    await open(t);
    await run(t, 'selec');
    await answer(t, db, stream, data: {'ok': false, 'error': 'ERROR 1064'});
    expect(find.text('ERROR 1064'), findsOneWidget);
  });

  testWidgets('malformed results say so instead of crashing', (t) async {
    await open(t);
    await run(t, 'select 1');
    await answer(t, db, stream, data: {'rows': 5});
    expect(find.textContaining('expected array'), findsOneWidget);
  });

  testWidgets('Hint sends the SQL, last result and history', (t) async {
    await open(t);
    await run(t, 'select 1');
    await answer(t, db, stream, data: runBadData);
    await t.tap(find.byKey(const ValueKey('hint')));
    await t.pump(const Duration(milliseconds: 50));
    var body = lastRequest(db).$2['body'] as Map;
    expect(body['sql'], 'select 1');
    expect((body['last_result'] as Map)['match'], false);
    expect(body.containsKey('history'), isFalse);
    await answer(t, db, stream, data: {'question': 'What is COUNT of NULL?'});
    expect(find.text('What is COUNT of NULL?'), findsOneWidget);
    await t.tap(find.byKey(const ValueKey('hint')));
    await t.pump(const Duration(milliseconds: 50));
    body = lastRequest(db).$2['body'] as Map;
    expect(body['history'], ['What is COUNT of NULL?']);
    await answer(t, db, stream, data: {'question': 'Which rows join?'});
    expect(find.text('Which rows join?'), findsOneWidget);
  });

  testWidgets('the typed SQL survives leaving the screen', (t) async {
    await open(t);
    await t.enterText(editor(), 'select 42');
    await t.pump();
    await t.pumpWidget(const SizedBox());
    await open(t);
    expect(find.text('select 42'), findsOneWidget);
  });

  group('predict', () {
    testWidgets('shows the query; Check sends the trimmed grid', (t) async {
      await open(t, drill: predictDrillData);
      expect(find.text('SELECT 1'), findsOneWidget);
      await t.enterText(find.byKey(const ValueKey('cell-0-0')), '2');
      await t.pump();
      await t.tap(find.byKey(const ValueKey('check')));
      await t.pump(const Duration(milliseconds: 50));
      final (_, req) = lastRequest(db);
      expect(req['kind'], 'sql_predict');
      expect(req['body'], {
        'id': 'basics-1',
        'grid': [
          ['2'],
        ],
      });
      await answer(
        t,
        db,
        stream,
        data: {
          'match': false,
          'actual_rows': [
            ['1'],
          ],
          'cell_diff': [
            [0, 0, '2', '1'],
          ],
        },
      );
      expect(find.byKey(const ValueKey('mark-0-0')), findsWidgets);
      expect(find.text('1'), findsWidgets);
    });

    for (final (match, icon) in [
      (true, Icons.check_circle_outline),
      (false, Icons.cancel_outlined),
    ]) {
      testWidgets('a predicted ERROR (match $match) shows the verdict and '
          'the real error', (t) async {
        await open(t, drill: predictDrillData);
        await t.enterText(find.byKey(const ValueKey('cell-0-0')), 'ERROR');
        await t.pump();
        await t.tap(find.byKey(const ValueKey('check')));
        await t.pump(const Duration(milliseconds: 50));
        await answer(
          t,
          db,
          stream,
          data: {
            'match': match,
            'error': 'ERROR 1054 (42S22): Unknown column',
            'actual_rows': [
              ['ERROR 1054'],
            ],
          },
        );
        expect(find.byIcon(icon), findsOneWidget);
        expect(find.textContaining('Unknown column'), findsOneWidget);
      });
    }

    testWidgets('rows and columns can be added and removed', (t) async {
      await open(t, drill: predictDrillData);
      expect(find.byKey(const ValueKey('cell-1-0')), findsOneWidget);
      await t.tap(find.byKey(const ValueKey('add-row')));
      await t.pump();
      expect(find.byKey(const ValueKey('cell-2-0')), findsOneWidget);
      await t.tap(find.byKey(const ValueKey('remove-row')));
      await t.pump();
      expect(find.byKey(const ValueKey('cell-2-0')), findsNothing);
      await t.tap(find.byKey(const ValueKey('add-col')));
      await t.pump();
      expect(find.byKey(const ValueKey('cell-0-2')), findsOneWidget);
      await t.tap(find.byKey(const ValueKey('remove-col')));
      await t.pump();
      expect(find.byKey(const ValueKey('cell-0-2')), findsNothing);
    });
  });
}
