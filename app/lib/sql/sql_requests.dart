/// Request bodies of the SQL practice kinds (`DOCS-contract-sql.md`).
library;

import 'dart:math';

import 'package:tutor/model/json.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/sql/sql_models.dart';

/// `sql_list`.
RequestBody sqlList() => const RequestBody.raw(RequestKind.sqlList, {});

/// `sql_get`.
RequestBody sqlGet(String id) =>
    RequestBody.raw(RequestKind.sqlGet, {'id': id});

/// `sql_run`: [sql] against drill [id].
RequestBody sqlRun(String id, String sql) =>
    RequestBody.raw(RequestKind.sqlRun, {'id': id, 'sql': sql});

/// `sql_predict`: the typed output [grid].
RequestBody sqlPredict(String id, Grid grid) =>
    RequestBody.raw(RequestKind.sqlPredict, {'id': id, 'grid': grid});

/// Most earlier hints a request carries, and the longest one (the worker
/// refuses more).
const maxHintHistory = 10;

/// Longest hint line the worker takes.
const maxHintChars = 500;

/// `sql_hint`: one Socratic question; [history] holds the earlier ones, the
/// last [maxHintHistory] cut to [maxHintChars] (RTDB drops an empty list,
/// so none is absent).
RequestBody sqlHint(
  String id, {
  required List<String> history,
  String? sql,
  Json? lastResult,
}) => RequestBody.raw(
  RequestKind.sqlHint,
  compact({
    'id': id,
    'sql': sql,
    'last_result': lastResult,
    'history': _history(history),
  }),
);

/// `sql_generate`: a new drill on [topic].
RequestBody sqlGenerate(String topic) =>
    RequestBody.raw(RequestKind.sqlGenerate, {'topic': topic});

/// `sql_lesson_turn`: no [lessonId] starts a lesson, a [lessonId] alone
/// resumes it, with an [answer] it grades the pending question.
RequestBody sqlLessonTurn(String topic, {String? lessonId, String? answer}) =>
    RequestBody.raw(
      RequestKind.sqlLessonTurn,
      compact({'topic': topic, 'lesson_id': lessonId, 'answer': answer}),
    );

List<String>? _history(List<String> history) {
  if (history.isEmpty) return null;
  final recent = history.length > maxHintHistory
      ? history.sublist(history.length - maxHintHistory)
      : history;
  return [for (final h in recent) h.substring(0, min(h.length, maxHintChars))];
}
