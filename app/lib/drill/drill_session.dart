/// The drill (model-free fallback): `drill_next` -> pick -> `drill_answer`.
/// One request at a time through a [RequestRunner]; a failed one keeps the
/// screen as it was and offers [DrillSession.retry].
library;

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';

/// Where the drill stands.
enum DrillStage {
  /// A request is out.
  loading,

  /// A question is shown, nothing picked.
  question,

  /// A pick was graded; the back is shown.
  answered,

  /// Nothing to drill.
  empty,

  /// The last request failed ([DrillSession.error]).
  failed,
}

/// State of one drill run.
class DrillSession extends ChangeNotifier {
  /// Creates the run; [unavailable] seeds the banner (the auto-switch).
  new({required this.runner, this.subject, this.unavailable});

  /// Runs the requests.
  final RequestRunner runner;

  /// Only this subject is drilled (null: any).
  final String? subject;

  /// Claude-out banner source; the latest PC answer wins.
  Unavailable? unavailable;

  /// Stage.
  DrillStage stage = DrillStage.loading;

  /// The current question (also while answered).
  DrillQuestion? question;

  /// The grading, once picked.
  DrillAnswer? answer;

  /// The picked option, once picked.
  int? picked;

  /// The day's minutes (latest known).
  DrillToday? today;

  /// Text for the failed stage.
  String? error;

  bool _disposed = false;
  Future<void> Function()? _again;

  /// Asks for the next question.
  Future<void> next() => _go(() async {
    final data = await _call(RequestBody.drillNext(subject: subject));
    if (data == null) return;
    switch (DrillNext.fromJson(data)) {
      case DrillEmpty():
        question = null;
        _stage(DrillStage.empty);
      case final DrillQuestion q:
        question = q;
        answer = picked = null;
        today = q.today;
        unavailable = q.unavailable ?? unavailable;
        _stage(DrillStage.question);
    }
  });

  /// Grades option [choice] of the current question.
  Future<void> pick(int choice) {
    final q = question;
    if (q == null || stage != DrillStage.question) return Future.value();
    return _go(() async {
      final data = await _call(RequestBody.drillAnswer(q.promptId, choice));
      if (data == null) return;
      picked = choice;
      answer = DrillAnswer.fromJson(data);
      today = answer!.today;
      _stage(DrillStage.answered);
    });
  }

  /// Repeats the request that failed.
  Future<void> retry() => _again?.call() ?? Future.value();

  // Runs [step] as the one in flight; a malformed reply or a failed
  // request lands in the failed stage, never as an uncaught error.
  Future<void> _go(Future<void> Function() step) async {
    _again = () => _go(step);
    _stage(DrillStage.loading);
    try {
      await step();
    } on FormatException catch (e) {
      error = 'Unreadable reply: ${e.message}';
    }
    if (stage == DrillStage.loading) _stage(DrillStage.failed);
  }

  Future<Json?> _call(RequestBody body) async {
    final status = await runner.run(body);
    switch (status) {
      case RelayDone(:final data):
        error = null;
        return data;
      case RelayNotSent():
        error = status.text;
      case RelayFailed(:final text):
        error = text;
      default:
        error = 'The PC did not answer.';
    }
    return null;
  }

  void _stage(DrillStage s) {
    stage = s;
    _notify();
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    unawaited(runner.dispose());
    super.dispose();
  }
}
