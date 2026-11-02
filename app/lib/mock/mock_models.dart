/// Wire models of the `mock` request kind (server `tutor/relay/mock.py`).
library;

import 'package:tutor/model/json.dart';
import 'package:tutor/sql/sql_models.dart';

/// Task sections, in test order.
enum MockSection {
  /// Read a snippet, pick its output.
  pyMcq('py_mcq'),

  /// Write a Python function.
  pyCode('py_code'),

  /// Write a MySQL query.
  sql('sql');

  new(this.wire);

  /// Name on the wire.
  final String wire;

  /// Whether the answer is typed code.
  bool get typed => this != pyMcq;

  /// Parses a wire name.
  static MockSection parse(String s) => byWire(values, s, (v) => v.wire);
}

/// One question of the paper; the answer key never reaches the app.
typedef MockTask = ({
  String id,
  MockSection section,
  String title,
  String topic,
  String prompt,
  String code,
  List<String> options,
  String starter,
  List<SqlTable> tables,
  Grid sample,
});

/// A started test: the clock and the tasks.
typedef MockPaper = ({
  String mockId,
  int startedMs,
  int deadlineMs,
  int minutes,
  List<MockTask> tasks,
  List<String> notes,
});

/// A "go study this" target of a missed item.
typedef MockLink = ({String kind, String target});

/// One graded task; `detail` is the section's raw object.
typedef MockItem = ({
  String id,
  MockSection section,
  String title,
  String topic,
  bool correct,
  String? answer,
  Json detail,
  MockLink? link,
});

/// The graded test.
typedef MockResult = ({
  int score,
  int total,
  int percent,
  List<MockItem> items,
});

Grid _grid(Object? v) => [
  for (final r in (v as List<dynamic>? ?? const []))
    [for (final c in r as List<dynamic>) '${c ?? 'NULL'}'],
];

MockTask _task(Object? v) {
  final j = asJson(v, 'tasks');
  return (
    id: str(j, 'id'),
    section: MockSection.parse(str(j, 'section')),
    title: strOr(j, 'title') ?? '',
    topic: strOr(j, 'topic') ?? '',
    prompt: strOr(j, 'prompt_md') ?? '',
    code: strOr(j, 'code') ?? '',
    options: strings(j, 'options'),
    starter: strOr(j, 'starter') ?? '',
    tables: parseTables(j['tables']),
    sample: _grid(j['sample']),
  );
}

/// Parses a `start` (or `get`) result.
MockPaper parsePaper(Json j) {
  final minutes = intOr(j, 'minutes') ?? 60;
  final started = integer(j, 'started_ms');
  return (
    mockId: str(j, 'mock_id'),
    startedMs: started,
    deadlineMs: intOr(j, 'deadline_ms') ?? started + minutes * 60000,
    minutes: minutes,
    tasks: listOf(j, 'tasks', _task),
    notes: strings(j, 'notes'),
  );
}

MockLink? _link(Json j) {
  final l = objOr(j, 'link');
  if (l == null) return null;
  final kind = str(l, 'kind');
  final target = kind == 'coach' ? strOr(l, 'slug') : strOr(l, 'topic');
  return target == null ? null : (kind: kind, target: target);
}

MockItem _item(Object? v) {
  final j = asJson(v, 'tasks');
  return (
    id: str(j, 'id'),
    section: MockSection.parse(str(j, 'section')),
    title: strOr(j, 'title') ?? '',
    topic: strOr(j, 'topic') ?? '',
    correct: flag(j, 'correct'),
    answer: strOr(j, 'answer'),
    detail: objOr(j, 'detail') ?? const {},
    link: _link(j),
  );
}

/// Parses a `finish` result.
MockResult parseResult(Json j) {
  final items = listOf(j, 'tasks', _item);
  final score = intOr(j, 'score') ?? items.where((i) => i.correct).length;
  final total = intOr(j, 'total') ?? items.length;
  return (
    score: score,
    total: total,
    percent: intOr(j, 'percent') ?? (total == 0 ? 0 : 100 * score ~/ total),
    items: items,
  );
}

/// The actual output of a `run`: a SQL grid or per-example verdicts.
typedef MockRun = ({
  bool ok,
  String? error,
  List<String> columns,
  Grid rows,
  List<MockExample> examples,
});

/// One visible example of a Python `run`.
typedef MockExample = ({
  int n,
  bool ok,
  String input,
  String expected,
  String actual,
  String? error,
});

String _show(Object? v) => v is String ? '"$v"' : '$v';

/// Parses one example of a `run` or of a failed-example list.
MockExample parseExample(Object? v) {
  final j = asJson(v, 'examples');
  return (
    n: intOr(j, 'n') ?? 0,
    ok: flag(j, 'ok'),
    input: _show(j['input']),
    expected: _show(j['expected']),
    actual: _show(j['actual']),
    error: strOr(j, 'error'),
  );
}

/// Parses a `run` result.
MockRun parseRun(Json j) => (
  ok: flag(j, 'ok', fallback: true),
  error: strOr(j, 'error'),
  columns: strings(j, 'columns'),
  rows: _grid(j['rows']),
  examples: listOf(j, 'examples', parseExample),
);
