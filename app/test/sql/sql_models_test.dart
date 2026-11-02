import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sql/sql_models.dart';
import 'package:tutor/sql/sql_requests.dart';

import 'sql_fixtures.dart';

void main() {
  test('list: drills, topics; absent lists are empty', () {
    final l = parseDrillList(listData);
    expect(l.topics, ['basics', 'joins-null']);
    expect(l.drills.length, 3);
    expect(l.drills.first.title, 'Count rows');
    expect(l.drills[1].predict, isTrue);
    expect(l.drills[2].generated, isTrue);
    expect(parseDrillList(const {}).drills, isEmpty);
  });

  test('drill: nested meta, tables, preview, query', () {
    final d = parseDrill(writeDrillData);
    expect(d.meta.id, 'basics-1');
    expect(d.taskMd, contains('Count'));
    expect(d.tables.single.name, 'emp');
    expect(d.tables.single.columns, ['id', 'name']);
    expect(d.tables.single.rows, [
      ['1', 'Ann'],
      ['2', 'NULL'],
    ]);
    expect(d.preview, [
      ['2'],
    ]);
    final p = parseDrill(predictDrillData);
    expect(p.meta.predict, isTrue);
    expect(p.query, 'SELECT 1');
  });

  test('a list RTDB turned into an index map still parses', () {
    final d = parseDrill({
      ...writeDrillData,
      'expected_preview': {
        '0': {'0': 7},
        '1': {'0': 8},
      },
    });
    expect(d.preview, [
      ['7'],
      ['8'],
    ]);
  });

  test('an object that is not an index map is an error', () {
    expect(
      () => parseOutcome(const {
        'rows': {'a': 1},
      }),
      throwsA(isA<FormatException>()),
    );
  });

  test('result: grids, diff, extra and missing rows', () {
    final r = parseOutcome(runBadData);
    expect(r.ok, isTrue);
    expect(r.match, isFalse);
    expect(r.columns, ['n']);
    expect(r.rows, [
      ['3'],
      ['NULL'],
    ]);
    expect(r.expectedRows, [
      ['2'],
    ]);
    expect(r.diff.single, (row: 0, col: 0, expected: '2', actual: '3'));
    expect(r.marked(expected: false), {(0, 0), (1, 0)});
    expect(r.marked(expected: true), {(0, 0)});
  });

  test('hintSlice keeps what the worker reads, trimmed', () {
    final slice = parseOutcome(runBadData).hintSlice();
    expect(slice['match'], false);
    expect(slice['rows'], [
      ['3'],
      ['NULL'],
    ]);
    expect(slice['cell_diff'], [
      [0, 0, '2', '3'],
    ]);
    final empty = parseOutcome(const {'ok': false, 'error': 'x'}).hintSlice();
    expect(empty.keys, unorderedEquals(['ok', 'error', 'match']));
  });

  test('result: error and empty rows', () {
    final r = parseOutcome(const {'ok': false, 'error': 'syntax'});
    expect(r.ok, isFalse);
    expect(r.error, 'syntax');
    expect(r.rows, isEmpty);
    expect(r.diff, isEmpty);
    expect(r.marked(expected: false), isEmpty);
  });

  test('prediction result uses actual_rows', () {
    final r = parseOutcome(const {
      'match': false,
      'actual_rows': [
        ['1'],
      ],
      'cell_diff': [
        [0, 0, '2', '1'],
      ],
    });
    expect(r.rows, [
      ['1'],
    ]);
    expect(r.ok, isTrue);
    expect(r.diff.single.actual, '1');
  });

  test('a bad type fails loudly', () {
    expect(() => parseDrill(const {'id': 3}), throwsA(isA<FormatException>()));
  });

  test('bodies carry the contract fields', () {
    final run = sqlRun('d1', 'select 1');
    expect(run.kind.wire, 'sql_run');
    expect(run.body, {'id': 'd1', 'sql': 'select 1'});
    expect(sqlList().body, isEmpty);
    expect(sqlGet('d1').body, {'id': 'd1'});
    expect(sqlGenerate('basics').body, {'topic': 'basics'});
    final pred = sqlPredict('d1', const [
      ['1', 'a'],
    ]);
    expect(pred.body['grid'], [
      ['1', 'a'],
    ]);
    final hint = sqlHint(
      'd1',
      sql: 'select',
      lastResult: const {'ok': true},
      history: const ['why?'],
    );
    expect(hint.body, {
      'id': 'd1',
      'sql': 'select',
      'last_result': {'ok': true},
      'history': ['why?'],
    });
    expect(sqlHint('d1', history: const []).body, {'id': 'd1'});
    final long =
        sqlHint(
              'd1',
              history: [for (var i = 0; i < 12; i++) '$i${'x' * 600}'],
            ).body['history']!
            as List<String>;
    expect(long.length, maxHintHistory);
    expect(long.first.startsWith('2'), isTrue);
    expect(long.every((h) => h.length == maxHintChars), isTrue);
  });

  test('trimGrid drops blank trailing rows and columns', () {
    expect(
      trimGrid([
        ['1', '', ''],
        ['', '', ''],
        ['2', 'x', ''],
        ['', '', ''],
      ]),
      [
        ['1', ''],
        ['', ''],
        ['2', 'x'],
      ],
    );
    expect(
      trimGrid([
        [''],
      ]),
      isEmpty,
    );
  });
}
