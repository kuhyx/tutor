/// A request's status as a cue (textgate): kind + glyph instead of the
/// worker's or the app's sentence. The sentence stays the spoken label
/// (`error_text.dart`, `blocked.dart`); only the kind and glyph are painted.
library;

import 'package:flutter/material.dart';
import 'package:tutor/relay/blocked.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/widgets/cue_chip.dart';

/// What a [RelayStatus] looks like: kind, glyph and the spoken sentence.
typedef RelayCue = ({CueKind kind, IconData? icon, String semanticLabel});

/// The call-to-action glyph of a block: what fixes it.
IconData blockedIcon(Blocked b) => switch (b.code) {
  dailyNewCap => Icons.add_circle_outline,
  lockedCode => b.reviewsModule ? Icons.replay : Icons.lock_outline,
  _ => switch (b.next) {
    BlockedNext.reviewModule => Icons.replay,
    BlockedNext.reviewsDue => Icons.schedule,
    BlockedNext.liftCap => Icons.add_circle_outline,
    BlockedNext.none => Icons.inventory_2_outlined,
  },
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
    ),
    RelayQueued() => (
      kind: CueKind.pending,
      icon: Icons.hourglass_top,
      semanticLabel: 'Sent; waiting for the PC...',
    ),
    RelayWorking(:final phase) => (
      kind: CueKind.pending,
      icon: null,
      semanticLabel: phaseText(phase),
    ),
    RelayNotSent(:final text) => (
      kind: CueKind.error,
      icon: Icons.cloud_off,
      semanticLabel: text,
    ),
    RelayFailed(blocked: final b?, :final text) => (
      kind: CueKind.blocked,
      icon: blockedIcon(b),
      semanticLabel: text,
    ),
    RelayFailed(:final text) => (
      kind: CueKind.error,
      icon: null,
      semanticLabel: text,
    ),
  };
}
