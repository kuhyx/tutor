/// One turn of a guided lesson (`sql_lesson_turn`, DOCS-contract-sql.md).
library;

import 'package:tutor/model/json.dart';
import 'package:tutor/sql/sql_models.dart';

/// The topics in the order the lessons walk them.
const lessonTopics = [
  'basics',
  'joins-null',
  'group-having',
  'pivot',
  'dates',
  'number-format',
  'window',
  'strings',
];

/// The next topic after [topic]; null after the last or an unknown one.
String? nextLessonTopic(String topic) {
  final i = lessonTopics.indexOf(topic);
  return i < 0 || i + 1 >= lessonTopics.length ? null : lessonTopics[i + 1];
}

/// One chat entry: the learner's text, or the tutor's markdown or a result.
typedef Bubble = ({bool mine, String? md, SqlTable? grid});

/// What the worker sent for one turn; markdown fields are null when absent.
typedef LessonTurn = ({
  String lessonId,
  String concept,
  int index,
  int total,
  bool check,
  String? questionMd,
  String? feedbackMd,
  String? summaryMd,
  List<SqlTable>? tables,
  SqlTable? result,
  bool done,
  List<Bubble>? thread,
});

/// Parses a lesson turn; `tables` stays null when the turn carries none.
LessonTurn parseLessonTurn(Json j) {
  final progress = objOr(j, 'progress') ?? const <String, dynamic>{};
  final result = objOr(j, 'result');
  final thread = j['thread'];
  return (
    lessonId: str(j, 'lesson_id'),
    concept: strOr(progress, 'concept') ?? '',
    index: intOr(progress, 'index') ?? 0,
    total: intOr(progress, 'total') ?? 0,
    check: strOr(progress, 'phase') == 'check',
    questionMd: strOr(j, 'question_md'),
    feedbackMd: strOr(j, 'feedback_md'),
    summaryMd: strOr(j, 'summary_md'),
    tables: j['tables'] == null ? null : parseTables(j['tables']),
    result: result == null ? null : parseTables({'': result}).single,
    done: flag(j, 'done'),
    thread: thread is List ? [for (final e in thread) _bubble(e)] : null,
  );
}

Bubble _bubble(Object? e) {
  if (e is! Map<String, dynamic>) throw const FormatException('thread entry');
  final grid = objOr(e, 'grid');
  return (
    mine: flag(e, 'mine'),
    md: strOr(e, 'md'),
    grid: grid == null ? null : parseTables({'': grid}).single,
  );
}
