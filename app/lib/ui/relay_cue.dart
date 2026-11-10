/// A request's status as a cue (textgate): kind + glyph instead of the
/// worker's or the app's sentence. A failed result's `kind`
/// (DOCS-relay-kinds.md, `relay_kinds.dart`) picks its glyph and a calm or
/// error tint; a phase picks the glyph beside the spinner. The app's own
/// sentence (`error_text.dart`, `blocked.dart`) is the spoken label only.
/// Unknown kinds and phases fall back to a generic glyph, never text.
library;

import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/relay/relay_kinds.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/widgets/cue_chip.dart';

/// What a `RelayStatus` looks like: kind, glyph and the spoken sentence;
/// `spin` = a spinner beside the glyph (a claimed request's phase).
typedef RelayCue = ({
  CueKind kind,
  IconData? icon,
  String semanticLabel,
  bool spin,
});

/// The glyph of a kind this build does not know.
const IconData fallbackErrorIcon = Icons.error_outline;

/// The glyph of a phase this build does not know.
const IconData workingIcon = Icons.more_horiz;

/// One glyph per result kind (the table in DOCS-relay-kinds.md).
const Map<String, IconData> kindIcons = {
  'err_bad_request': Icons.report_outlined,
  refusedPasteStatement: Icons.content_paste,
  'err_not_live': Icons.stop_circle_outlined,
  'err_session_live': Icons.play_disabled,
  'blocked_locked': Icons.lock_outline,
  'blocked_locked_review': Icons.replay,
  'blocked_cap': Icons.add_circle_outline,
  'blocked_no_card_none': Icons.inventory_2_outlined,
  'blocked_no_card_review': Icons.rate_review_outlined,
  'blocked_no_card_due': Icons.schedule,
  'err_unknown_card': Icons.search_off,
  'err_plan_conflict': Icons.merge_type,
  'err_edit_refused': Icons.edit_off,
  'err_focus_refused': Icons.do_not_disturb_alt,
  'err_model': Icons.running_with_errors,
  outageClaude: Icons.power_off,
  'err_unknown_prompt': Icons.help_outline,
  'err_gave_up': Icons.sync_disabled,
  'err_worker': Icons.bug_report_outlined,
};

/// The glyph of [kind]; unknown or null = [fallbackErrorIcon].
IconData kindIcon(String? kind) => kindIcons[kind] ?? fallbackErrorIcon;

/// A block or a refusal with a next step: the calm (call-to-action) tint,
/// not the error one. Decided by prefix, so a newer kind tints right too.
bool kindIsCalm(String? kind) =>
    kind != null &&
    (kind.startsWith('blocked_') || kind.startsWith('refused_'));

/// The glyph beside the spinner for [phase]; unknown = [workingIcon].
IconData phaseIcon(Phase phase) => switch (phase) {
  Phase.claimed => Icons.inbox_outlined,
  Phase.thinking => Icons.psychology_outlined,
  Phase.images => Icons.image_search,
  Phase.checkingImages => Icons.fact_check_outlined,
  Phase.publishing => Icons.publish,
  Phase.unknown => workingIcon,
};

/// The cue for [s]; null = nothing to show (idle or done). [stalled] is the
/// sentence once the runner is stalled (no result, no progress for minutes).
RelayCue? relayCue(RelayStatus? s, {String? stalled}) {
  final lost = stalled;
  return switch (s) {
    null || RelayDone() => null,
    RelayQueued() || RelayWorking() when lost != null => (
      kind: CueKind.error,
      icon: Icons.sync_problem,
      semanticLabel: lost,
      spin: false,
    ),
    RelayQueued() => (
      kind: CueKind.pending,
      icon: Icons.hourglass_top,
      semanticLabel: 'Sent; waiting for the PC...',
      spin: false,
    ),
    RelayWorking(:final phase) => (
      kind: CueKind.pending,
      icon: phaseIcon(phase),
      semanticLabel: phaseText(phase),
      spin: true,
    ),
    RelayNotSent(:final text) => (
      kind: CueKind.error,
      icon: Icons.cloud_off,
      semanticLabel: text,
      spin: false,
    ),
    RelayFailed(:final kind, :final blocked, :final text) => (
      kind: blocked != null || kindIsCalm(kind)
          ? CueKind.blocked
          : CueKind.error,
      icon: kindIcon(kind),
      semanticLabel: text,
      spin: false,
    ),
  };
}

/// How far off a due time is, as an arc: full at [span] or more, empty
/// when due. No digits (textgate); the time itself is in the spoken label.
class DueRing extends StatefulWidget {
  /// Creates the ring for [dueAt] (ms); [now] is the clock (tests).
  const new(this.dueAt, {this.now, this.span = defaultSpan, super.key});

  /// The arc's full scale.
  static const defaultSpan = Duration(hours: 24);

  /// When reviews fall due (ms since epoch).
  final int dueAt;

  /// The clock; null = the wall clock.
  final DateTime Function()? now;

  /// A due time this far off (or more) draws a full ring.
  final Duration span;

  /// The arc's fill at [at]: remaining time over [span], in 0..1.
  double fillAt(DateTime at) {
    final left = dueAt - at.millisecondsSinceEpoch;
    return math.max(0, math.min(1, left / span.inMilliseconds)).toDouble();
  }

  @override
  State<DueRing> createState() => _DueRingState();
}

class _DueRingState extends State<DueRing> {
  // The arc shrinks as time passes: redrawn each minute, no animation (so
  // pumpAndSettle and reduced motion both see a still picture).
  late final Timer _tick;

  @override
  void initState() {
    super.initState();
    _tick = Timer.periodic(const Duration(minutes: 1), (_) => setState(() {}));
  }

  @override
  void dispose() {
    _tick.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final at = (widget.now ?? DateTime.now)();
    return ExcludeSemantics(
      child: SizedBox.square(
        dimension: IconTheme.of(context).size ?? 24,
        child: CircularProgressIndicator(
          value: widget.fillAt(at),
          strokeWidth: 3,
          color: cueColor(context, CueKind.blocked),
          backgroundColor: cueColor(
            context,
            CueKind.blocked,
          ).withValues(alpha: 0.2),
        ),
      ),
    );
  }
}
