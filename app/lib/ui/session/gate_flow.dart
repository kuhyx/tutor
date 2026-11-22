/// The module gate in the app (curriculum §6, kuhy 2026-11-22): a refusal
/// naming `gate_cards` opens that review at once; once every card is
/// passed, the ratings are flushed and the same request goes out again, so
/// the next module's first card starts with no extra click.
library;

import 'dart:developer';

import 'package:flutter/widgets.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/relay/blocked.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/review/review_items.dart';
import 'package:tutor/ui/nav.dart';

/// What became of a gate review.
enum GateOutcome {
  /// Every card passed.
  passed,

  /// Left before the end: the cards still wait.
  left,

  /// Nothing to review (the log already shows every card passed).
  empty,
}

/// How many times one request goes round the gate by itself: a review, the
/// request again, and one retry for a worker that has not seen the
/// ratings yet. Never a loop.
const int gateRounds = 3;

/// The blocked result in [status] that names cards to review, if any.
Blocked? gateOf(RelayStatus status) => switch (status) {
  RelayFailed(:final blocked?) when blocked.gated => blocked,
  _ => null,
};

/// Opens the review of [blocked]'s `gate_cards` (minus any passed since);
/// [hint] is the screen's subject when the result names none.
Future<GateOutcome> runGate(
  BuildContext context,
  TutorServices s,
  Blocked blocked, {
  String? hint,
  DateTime Function() now = DateTime.now,
}) async {
  final subjects = await s.catalog.cached();
  final id = blocked.subjectId(subjects, hint: hint);
  if (id == null) return GateOutcome.empty;
  final items = await gateItems(
    catalog: s.catalog,
    events: s.events,
    subject: id,
    cards: blocked.gateCards,
    now: now().toUtc(),
  );
  if (items.isEmpty || !context.mounted) return GateOutcome.empty;
  final title =
      blocked.moduleTitle ?? blocked.subjectTitle ?? subjects[id]?.meta.title;
  final passed = await openGateReview(
    context,
    s,
    GateReview(subject: id, items: items, title: title),
  );
  return passed ? GateOutcome.passed : GateOutcome.left;
}

/// Sends the review's ratings, so the worker sees them before the next
/// request; offline they stay queued (the worker then refuses again and
/// the review glyph stays).
Future<void> flushRatings(TutorServices s) async {
  try {
    await s.events.flush();
  } on Exception catch (error) {
    log('gate flush failed; ratings kept queued', level: 800, error: error);
  }
}

/// Runs [send] and walks the module gate: each gated refusal opens its
/// review, and a passed review sends the request again (at most
/// [gateRounds] times). Returns the last status.
Future<RelayStatus> throughGate(
  BuildContext context,
  TutorServices s,
  Future<RelayStatus> Function() send, {
  String? hint,
  DateTime Function() now = DateTime.now,
}) async {
  var status = await send();
  for (var round = 0; round < gateRounds; round++) {
    final blocked = gateOf(status);
    if (blocked == null || !context.mounted) break;
    final outcome = await runGate(context, s, blocked, hint: hint, now: now);
    // Left early: the review glyph stays. Empty twice: the worker still
    // has not seen the ratings; the glyph stays rather than loop.
    if (outcome == GateOutcome.left) break;
    if (outcome == GateOutcome.empty && round > 0) break;
    await flushRatings(s);
    if (!context.mounted) break;
    status = await send();
  }
  return status;
}
