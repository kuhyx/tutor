/// `lc_run` and `lc_cards` results (DOCS-contract-coach.md).
library;

import 'package:tutor/coach/coach_list.dart';
import 'package:tutor/coach/coach_requests.dart';
import 'package:tutor/coach/coach_state.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/sql/sql_models.dart';

/// One statement example: text `got`/`expected`, or SQL rows and `diff`.
typedef ExampleRun = ({
  int n,
  bool ok,
  String? got,
  String? expected,
  String? error,
  List<String> columns,
  Grid rows,
  Grid expectedRows,
  List<CellDiff> diff,
});

/// An `lc_run` result; `held` = refused, see `note`.
typedef RunReport = ({
  CoachState? state,
  bool ok,
  String? error,
  bool noExamples,
  int passed,
  int total,
  List<ExampleRun> examples,
  bool held,
  String? note,
});

List<String> _row(Object? r) => [
  for (final c in items(r, 'row')) '${c ?? 'NULL'}',
];

Grid _grid(Object? v) => [for (final r in items(v, 'rows')) _row(r)];

CellDiff _diff(Object? v) {
  final c = _row(v);
  final row = c.length < 4 ? null : int.tryParse(c[0]);
  final col = c.length < 4 ? null : int.tryParse(c[1]);
  if (row == null || col == null) {
    throw const FormatException('"cell_diff": [row, col, expected, actual]');
  }
  return (row: row, col: col, expected: c[2], actual: c[3]);
}

ExampleRun _example(Object? v) {
  final j = asJson(v, 'examples');
  return (
    n: intOr(j, 'n') ?? 0,
    ok: flag(j, 'ok'),
    got: strOr(j, 'got'),
    expected: strOr(j, 'expected'),
    error: strOr(j, 'error'),
    columns: _row(j['columns']),
    rows: _grid(j['rows']),
    expectedRows: _grid(j['expected_rows']),
    diff: [for (final d in items(j['cell_diff'], 'cell_diff')) _diff(d)],
  );
}

/// Parses an `lc_run` result.
RunReport parseRunReport(Json j) {
  final all = [for (final e in items(j['examples'], 'examples')) _example(e)];
  return (
    state: parseState(j['state']),
    ok: flag(j, 'ok'),
    error: strOr(j, 'error'),
    noExamples: flag(j, 'no_examples'),
    passed: intOr(j, 'passed') ?? all.where((e) => e.ok).length,
    total: intOr(j, 'total') ?? all.length,
    examples: all,
    held: flag(j, 'held'),
    note: strOr(j, 'note'),
  );
}

/// A tutor card made from the session.
typedef CoachCard = ({String id, String front, String back, bool isNew});

/// A proposed entry the coach refused, with its reason.
typedef Refusal = ({String name, String reason});

/// An `lc_cards` result: cards, entries to confirm, refusals, Anki line.
typedef CoachCards = ({
  CoachState? state,
  List<CoachCard> cards,
  List<ToolboxEntry> proposals,
  List<Refusal> refused,
  String? ankiLine,
});

ToolboxEntry _entry(Object? v) {
  final j = asJson(v, 'proposals');
  return (
    name: str(j, 'name'),
    aliases: strings(j, 'aliases'),
    properties: strings(j, 'properties'),
  );
}

CoachCard _card(Object? v) {
  final j = asJson(v, 'cards');
  return (
    id: str(j, 'id'),
    front: strOr(j, 'front') ?? '',
    back: strOr(j, 'back') ?? '',
    isNew: flag(j, 'new'),
  );
}

Refusal _refusal(Object? v) {
  final j = asJson(v, 'refused');
  return (name: str(j, 'name'), reason: strOr(j, 'reason') ?? '');
}

/// Parses an `lc_cards` result.
CoachCards parseCoachCards(Json j) {
  final anki = objOr(j, 'anki');
  return (
    state: parseState(j['state']),
    cards: [for (final c in items(j['cards'], 'cards')) _card(c)],
    proposals: [for (final p in items(j['proposals'], 'proposals')) _entry(p)],
    refused: [for (final r in items(j['refused'], 'refused')) _refusal(r)],
    ankiLine: anki == null ? null : strOr(anki, 'line'),
  );
}
