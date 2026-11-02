/// One coach turn (the result of `lc_open`, `lc_turn`): every field is
/// optional on the wire; the screen keeps what an earlier turn gave.
/// Provisional shape (handoff 20261102-problem-coach-contract s7);
/// DOCS-contract-coach.md wins.
library;

import 'package:tutor/coach/coach_run.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/sql/lesson_models.dart';
import 'package:tutor/sql/sql_models.dart';

export 'package:tutor/coach/coach_list.dart';
export 'package:tutor/coach/coach_run.dart';

/// The problem, sent on start and on resume.
typedef Problem = ({
  String slug,
  String title,
  String difficulty,
  String statementMd,
  Map<String, String> starter,
});

/// What to keep above the answer box: markdown (a code fence, a table) or
/// a parsed table.
typedef Pin = ({String? md, SqlTable? table});

/// One turn. `step` is 1-5, `rung` the hint rung (`H0`-`H3`), `turn` and
/// `budget` the turn counter, `banner` a notice from the worker (re-test:
/// do not submit on LeetCode; budget reached), `thread` the whole stored
/// conversation (resume only).
typedef CoachTurn = ({
  String lcId,
  Problem? problem,
  int? step,
  String? rung,
  int? turn,
  int? budget,
  bool retest,
  String? banner,
  String? replyMd,
  Pin? pin,
  List<Bubble>? thread,
  bool ended,
  PostMortem? postmortem,
});

/// Parses a coach turn. Without a `pin` the last code block or table of the
/// reply is pinned: a question about it never sends the learner scrolling.
CoachTurn parseCoachTurn(Json j) {
  final reply = strOr(j, 'msg_md');
  final pin = objOr(j, 'pin');
  final problem = objOr(j, 'problem');
  final post = objOr(j, 'postmortem');
  final fallback = reply == null ? null : extractPin(reply);
  return (
    lcId: str(j, 'lc_id'),
    problem: problem == null ? null : _problem(problem),
    step: intOr(j, 'step'),
    rung: strOr(j, 'rung'),
    turn: intOr(j, 'turn'),
    budget: intOr(j, 'budget'),
    retest: flag(j, 'retest'),
    banner: strOr(j, 'banner'),
    replyMd: reply,
    pin: pin != null
        ? _pin(pin)
        : fallback == null
        ? null
        : (md: fallback, table: null),
    thread: j['thread'] == null
        ? null
        : [for (final e in _list(j['thread'])) parseBubble(e)],
    ended: flag(j, 'ended'),
    postmortem: post == null ? null : parsePostMortem(post),
  );
}

List<Object?> _list(Object? v) =>
    v is List ? v : throw const FormatException('"thread": expected array');

Problem _problem(Json j) {
  final slug = str(j, 'slug');
  return (
    slug: slug,
    title: strOr(j, 'title') ?? slug,
    difficulty: strOr(j, 'difficulty') ?? '',
    statementMd: strOr(j, 'statement_md') ?? '',
    starter: mapOf(
      j,
      'starter',
      (v) => v is String ? v : throw const FormatException('"starter"'),
    ),
  );
}

Pin _pin(Json j) {
  final t = objOr(j, 'table');
  return (
    md: strOr(j, 'md'),
    table: t == null ? null : parseTables({strOr(t, 'name') ?? '': t}).single,
  );
}

final _fence = RegExp(r'```[^\n]*\n.*?```', dotAll: true);
final _rule = RegExp(r'^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?$');

/// The last fenced block or pipe table of `md`, as markdown; null if none.
String? extractPin(String md) {
  final fence = _fence.allMatches(md).lastOrNull;
  final lines = md.split('\n');
  var offset = 0;
  var tableEnd = -1;
  String? table;
  for (var i = 0; i < lines.length; i++) {
    final isTable =
        lines[i].trim().startsWith('|') &&
        i + 1 < lines.length &&
        _rule.hasMatch(lines[i + 1].trim());
    if (!isTable) {
      offset += lines[i].length + 1;
      continue;
    }
    var j = i;
    final start = offset;
    while (j < lines.length && lines[j].trim().startsWith('|')) {
      offset += lines[j].length + 1;
      j++;
    }
    table = lines.sublist(i, j).join('\n').trim();
    tableEnd = start + table.length;
    i = j - 1;
  }
  if (fence != null && fence.end >= tableEnd) return fence.group(0);
  return table;
}
