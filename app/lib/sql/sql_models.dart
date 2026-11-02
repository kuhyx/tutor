/// The SQL practice wire shapes: drills, tables, run and prediction results.
///
/// RTDB drops empty lists and nulls, and may hand a list back as an
/// index-keyed map, so every list goes through [_items] and every cell
/// through [_cell] (NULL is the text `NULL`, numbers are text).
library;

import 'package:tutor/model/json.dart';

/// Rows of cells.
typedef Grid = List<List<String>>;

/// The listing line of one drill.
typedef DrillMeta = ({
  String id,
  String title,
  String topic,
  bool predict,
  bool generated,
});

/// A table the task refers to.
typedef SqlTable = ({String name, List<String> columns, Grid rows});

/// One drill: the task, its tables and, per kind, what to show.
typedef Drill = ({
  DrillMeta meta,
  String taskMd,
  List<SqlTable> tables,
  String query,
  Grid preview,
});

/// `sql_list`: every drill and the topic names.
typedef DrillList = ({List<DrillMeta> drills, List<String> topics});

/// One mismatching cell, 0-based.
typedef CellDiff = ({int row, int col, String expected, String actual});

List<Object?> _items(Object? v, String what) {
  if (v == null) return const [];
  if (v is List) return v;
  if (v is Map) {
    final keys = v.keys.map((k) => int.tryParse('$k')).toList();
    if (keys.contains(null)) {
      throw FormatException('"$what": expected array, got object');
    }
    final sorted = v.entries.toList()
      ..sort((a, b) => int.parse('${a.key}').compareTo(int.parse('${b.key}')));
    return [for (final e in sorted) e.value];
  }
  throw FormatException('"$what": expected array, got ${v.runtimeType}');
}

String _cell(Object? v) => v == null ? 'NULL' : '$v';

Grid _grid(Object? v, String what) => [
  for (final row in _items(v, what))
    [for (final c in _items(row, what)) _cell(c)],
];

List<String> _names(Object? v, String what) => [
  for (final c in _items(v, what)) _cell(c),
];

DrillMeta _meta(Json j) => (
  id: str(j, 'id'),
  title: strOr(j, 'title') ?? str(j, 'id'),
  topic: strOr(j, 'topic') ?? '',
  predict: strOr(j, 'kind') == 'predict',
  generated: strOr(j, 'source') == 'generated',
);

/// Parses a `sql_list` result.
DrillList parseDrillList(Json j) => (
  drills: [
    for (final d in _items(j['drills'], 'drills')) _meta(asJson(d, 'drills')),
  ],
  topics: _names(j['topics'], 'topics'),
);

/// Tables from `{name: {columns, rows}}`; absent = none.
List<SqlTable> parseTables(Object? v) {
  final tables = v == null ? <String, dynamic>{} : asJson(v, 'tables');
  return [
    for (final e in tables.entries)
      (
        name: e.key,
        columns: _names(asJson(e.value, e.key)['columns'], e.key),
        rows: _grid(asJson(e.value, e.key)['rows'], e.key),
      ),
  ];
}

/// Parses a `sql_get` result; `meta` may be nested or flat.
Drill parseDrill(Json j) => (
  meta: _meta(objOr(j, 'meta') ?? j),
  taskMd: strOr(j, 'task_md') ?? '',
  tables: parseTables(j['tables']),
  query: strOr(j, 'query') ?? '',
  preview: _grid(j['expected_preview'], 'expected_preview'),
);

/// A `sql_run` or `sql_predict` result.
class SqlOutcome {
  /// Creates the outcome.
  const new({
    required this.ok,
    required this.error,
    required this.columns,
    required this.rows,
    required this.expectedRows,
    required this.match,
    required this.diff,
    required this.raw,
  });

  /// False when the SQL failed to run (then [error] says why).
  final bool ok;

  /// The database's message.
  final String? error;

  /// Result column names.
  final List<String> columns;

  /// What the SQL (or the prediction's query) printed.
  final Grid rows;

  /// What the drill expects; empty when the result does not carry it.
  final Grid expectedRows;

  /// Exact match under the test's rules.
  final bool match;

  /// Mismatching cells.
  final List<CellDiff> diff;

  /// The decoded result, for the hint request.
  final Json raw;

  /// The part of this result a hint request carries (the worker reads
  /// only these, and the first 20 rows and diffs).
  Json hintSlice() => compact({
    'ok': ok,
    'error': error,
    'columns': columns.isEmpty ? null : columns,
    'match': match,
    'rows': rows.isEmpty ? null : rows.take(20).toList(),
    'cell_diff': diff.isEmpty
        ? null
        : [
            for (final d in diff.take(20)) [d.row, d.col, d.expected, d.actual],
          ],
  });

  /// Cells to highlight in the expected or the actual grid: the diff, plus
  /// every cell of a row the other grid does not have.
  Set<(int, int)> marked({required bool expected}) {
    final mine = expected ? expectedRows : rows;
    final other = expected ? rows : expectedRows;
    return {
      for (final d in diff) (d.row, d.col),
      if (other.isNotEmpty)
        for (var r = other.length; r < mine.length; r++)
          for (var c = 0; c < mine[r].length; c++) (r, c),
    };
  }
}

/// Parses a result; a prediction's `actual_rows` count as the rows.
SqlOutcome parseOutcome(Json j) {
  final error = strOr(j, 'error');
  return SqlOutcome(
    ok: flag(j, 'ok', fallback: error == null),
    error: error,
    columns: _names(j['columns'], 'columns'),
    rows: _grid(j['rows'] ?? j['actual_rows'], 'rows'),
    expectedRows: _grid(j['expected_rows'], 'expected_rows'),
    match: flag(j, 'match'),
    diff: [
      for (final d in _items(j['cell_diff'], 'cell_diff'))
        (
          row: _num(d, 0),
          col: _num(d, 1),
          expected: _cell(_items(d, 'cell_diff')[2]),
          actual: _cell(_items(d, 'cell_diff')[3]),
        ),
    ],
    raw: j,
  );
}

int _num(Object? d, int i) {
  final v = _items(d, 'cell_diff')[i];
  return v is num
      ? v.toInt()
      : throw const FormatException('cell_diff: bad index');
}

/// [grid] without blank trailing rows and columns (an untouched spare
/// row is not part of the prediction).
Grid trimGrid(Grid grid) {
  var rows = grid.length;
  while (rows > 0 && grid[rows - 1].every((c) => c.trim().isEmpty)) {
    rows--;
  }
  var cols = 0;
  for (final row in grid.take(rows)) {
    for (var c = row.length; c > cols; c--) {
      if (row[c - 1].trim().isNotEmpty) {
        cols = c;
        break;
      }
    }
  }
  return [
    for (final row in grid.take(rows)) [...row.take(cols)],
  ];
}
