/// Read mode's state: `read_next` -> flip -> `read_rate` -> `read_next`.
/// One request at a time through a [RequestRunner]; a failed one keeps the
/// screen as it was and offers [ReadSession.retry].
library;

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/drill/read_models.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';

/// Where read mode stands.
enum ReadStage {
  /// A request is out.
  loading,

  /// A card is shown (front, or both sides once [ReadSession.flipped]).
  card,

  /// Nothing left to read.
  empty,

  /// The last request failed ([ReadSession.error]).
  failed,
}

/// State of one read-mode run.
class ReadSession extends ChangeNotifier {
  /// Creates the run; [unavailable] seeds the outage glyph.
  new({required this.runner, this.subject, this.unavailable});

  /// Runs the requests.
  final RequestRunner runner;

  /// Only this subject is read (null: any).
  final String? subject;

  /// The outage glyph's source; the PC's latest answer wins.
  Unavailable? unavailable;

  /// Stage.
  ReadStage stage = ReadStage.loading;

  /// The open card.
  ReadPrompt? prompt;

  /// Whether the back is shown.
  bool flipped = false;

  /// Cards rated in this run.
  int rated = 0;

  /// Text for the failed stage.
  String? error;

  /// The worker's failure behind [error] (its codes pick the glyph).
  RelayFailed? failure;

  bool _disposed = false;
  Future<void> Function()? _again;

  /// Asks for the next card.
  Future<void> next() => _go(() async {
    final data = await _call(readNext(subject: subject));
    if (data == null) return;
    switch (ReadNext.fromJson(data)) {
      case ReadEmpty():
        prompt = null;
        _stage(ReadStage.empty);
      case final ReadPrompt p:
        prompt = p;
        flipped = false;
        unavailable = p.unavailable;
        _stage(ReadStage.card);
    }
  });

  /// Shows the back of the open card.
  void flip() {
    if (stage != ReadStage.card || flipped) return;
    flipped = true;
    _notify();
  }

  /// Rates the open card, then asks for the next one.
  Future<void> rate(ReadRating rating) {
    final p = prompt;
    if (p == null || stage != ReadStage.card || !flipped) {
      return Future.value();
    }
    return _go(() async {
      final data = await _call(readRate(p.promptId, rating));
      if (data == null) {
        // The PC forgot the card (restarted): rating it again never works.
        if (failure?.code == 'unknown_prompt') _again = next;
        return;
      }
      rated++;
      await next();
    });
  }

  /// Repeats the request that failed.
  Future<void> retry() => _again?.call() ?? Future.value();

  // Runs [step] as the one in flight; a malformed reply or a failed
  // request lands in the failed stage, never as an uncaught error.
  Future<void> _go(Future<void> Function() step) async {
    _again = () => _go(step);
    _stage(ReadStage.loading);
    try {
      await step();
    } on FormatException catch (e) {
      error = 'Unreadable reply: ${e.message}';
      failure = null;
    }
    if (stage == ReadStage.loading) _stage(ReadStage.failed);
  }

  Future<Json?> _call(RequestBody body) async {
    final status = await runner.run(body);
    switch (status) {
      case RelayDone(:final data):
        error = failure = null;
        return data;
      case RelayNotSent():
        error = status.text;
        failure = null;
      case RelayFailed(:final text):
        error = text;
        failure = status;
      default:
        error = 'The PC did not answer.';
        failure = null;
    }
    return null;
  }

  void _stage(ReadStage s) {
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
