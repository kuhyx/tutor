/// `lc_open` and `lc_turn` results (DOCS-contract-coach.md).
library;

import 'package:tutor/coach/coach_list.dart';
import 'package:tutor/coach/coach_state.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/sql/lesson_models.dart';

export 'package:tutor/coach/coach_list.dart';
export 'package:tutor/coach/coach_run.dart';
export 'package:tutor/coach/coach_state.dart';

/// An opened problem: `replyMd` (opener) or `thread` (resume).
typedef Opened = ({
  String lcId,
  String slug,
  String title,
  String difficulty,
  String kind,
  String lang,
  List<String> langs,
  String statementMd,
  Map<String, String> starter,
  bool retest,
  CoachState? state,
  String? replyMd,
  List<Bubble>? thread,
});

/// Parses an `lc_open` result.
Opened parseOpened(Json j) {
  final slug = str(j, 'slug');
  final kind = strOr(j, 'kind') ?? 'algo';
  final lang = strOr(j, 'lang') ?? (kind == 'sql' ? 'mysql' : defaultCoachLang);
  final langs = strings(j, 'langs');
  return (
    lcId: str(j, 'lc_id'),
    slug: slug,
    title: strOr(j, 'title') ?? slug,
    difficulty: strOr(j, 'difficulty') ?? '',
    kind: kind,
    lang: lang,
    langs: langs.isEmpty ? [lang] : langs,
    statementMd: strOr(j, 'statement_md') ?? '',
    starter: mapOf(
      j,
      'starter',
      (v) => v is String ? v : throw const FormatException('"starter"'),
    ),
    retest: flag(j, 'retest'),
    state: parseState(j['state']),
    replyMd: strOr(j, 'reply_md'),
    thread: j['thread'] == null
        ? null
        : [for (final e in items(j['thread'], 'thread')) parseBubble(e)],
  );
}

/// The `solved` verdict: what is `missing`; `summaryMd` once done.
typedef ExitInfo = ({bool ok, String? missing, String? summaryMd});

/// An `lc_turn` result; `held` = a verdict or refusal in `note`.
typedef CoachTurn = ({
  CoachState? state,
  String? replyMd,
  String? note,
  bool held,
  String? banner,
  List<String> choices,
  ExitInfo? exit,
});

/// Parses an `lc_turn` result.
CoachTurn parseCoachTurn(Json j) {
  final exit = objOr(j, 'exit');
  return (
    state: parseState(j['state']),
    replyMd: strOr(j, 'reply_md'),
    note: strOr(j, 'note'),
    held: flag(j, 'held'),
    banner: strOr(j, 'banner'),
    choices: strings(j, 'choices'),
    exit: exit == null
        ? null
        : (
            ok: flag(exit, 'ok'),
            missing: strOr(exit, 'missing'),
            summaryMd: strOr(exit, 'summary_md'),
          ),
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
