/// The result of `lc_run` (per-example got vs expected) and the post-mortem
/// that ends a session (summary table and the cards to confirm).
library;

import 'package:tutor/coach/coach_list.dart';
import 'package:tutor/coach/coach_requests.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/sql/sql_models.dart';

/// One statement example: `got` vs `expected` text, or tables for SQL; an
/// `error` name (`TypeError`) when the code threw.
typedef ExampleRun = ({
  int n,
  bool ok,
  String got,
  String expected,
  SqlTable? gotTable,
  SqlTable? expectedTable,
  String? error,
});

/// `lc_run` result: the `examples`, or a run-level `error` (`timeout`,
/// `no_examples`, `syntax`, ...).
typedef RunReport = ({String? error, List<ExampleRun> examples});

/// Parses an `lc_run` result.
RunReport parseRunReport(Json j) => (
  error: strOr(j, 'error'),
  examples: [
    for (final e in items(j['examples'], 'examples'))
      _example(asJson(e, 'examples')),
  ],
);

ExampleRun _example(Json j) => (
  n: intOr(j, 'n') ?? 0,
  ok: flag(j, 'ok'),
  got: strOr(j, 'got') ?? '',
  expected: strOr(j, 'expected') ?? '',
  gotTable: _table(j['got_table']),
  expectedTable: _table(j['expected_table']),
  error: strOr(j, 'error'),
);

SqlTable? _table(Object? v) => v == null ? null : parseTables({'': v}).single;

/// A tutor card the post-mortem made: the property list and its operation.
typedef CoachCard = ({String front, String back});

/// The summary table (markdown), the cards made, and the toolbox entries
/// waiting for the learner's confirmation.
typedef PostMortem = ({
  String? summaryMd,
  List<CoachCard> cards,
  List<ToolboxEntry> proposals,
});

/// Parses the `postmortem` object.
PostMortem parsePostMortem(Json j) => (
  summaryMd: strOr(j, 'summary_md'),
  cards: [
    for (final c in items(j['cards'], 'cards'))
      (
        front: strOr(asJson(c, 'cards'), 'front') ?? '',
        back: strOr(asJson(c, 'cards'), 'back') ?? '',
      ),
  ],
  proposals: [
    for (final p in items(j['proposals'], 'proposals'))
      (
        name: str(asJson(p, 'proposals'), 'name'),
        aliases: strings(asJson(p, 'proposals'), 'aliases'),
        properties: strings(asJson(p, 'proposals'), 'properties'),
      ),
  ],
);
