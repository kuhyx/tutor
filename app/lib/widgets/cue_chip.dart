/// Status without sentences: a tinted glyph chip. An error shakes once
/// (unless animations are off) in red with the error glyph; busy spins; a
/// block shows its call-to-action glyph. The old sentence is the spoken
/// label (a live region), never painted.
library;

import 'dart:math' as math;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// What a cue says.
enum CueKind {
  /// Something failed (red, error glyph, shake).
  error,

  /// Waiting or working (spinner).
  pending,

  /// Blocked: a next step, not a failure (amber, the step's glyph).
  blocked,

  /// Done or saved (green check).
  ok,

  /// Offline (cloud crossed out).
  offline,
}

/// The default glyph of [kind].
IconData cueIcon(CueKind kind) => switch (kind) {
  CueKind.error => Icons.error_outline,
  CueKind.pending => Icons.hourglass_top,
  CueKind.blocked => Icons.lock_clock_outlined,
  CueKind.ok => Icons.check_circle_outline,
  CueKind.offline => Icons.cloud_off,
};

/// The tint of [kind].
Color cueColor(BuildContext context, CueKind kind) => switch (kind) {
  CueKind.error => Theme.of(context).colorScheme.error,
  CueKind.pending => Theme.of(context).colorScheme.primary,
  CueKind.blocked => AppPalette.warning,
  CueKind.ok => AppPalette.success,
  CueKind.offline => Theme.of(context).colorScheme.onSurfaceVariant,
};

/// A status cue: glyph (or spinner) on a tinted chip.
class CueChip extends StatefulWidget {
  /// Creates the cue; [icon] overrides the kind's glyph.
  const new({
    required this.kind,
    required this.semanticLabel,
    this.icon,
    this.trailing = const [],
    super.key,
  });

  /// What it says.
  final CueKind kind;

  /// The old sentence, spoken only.
  final String semanticLabel;

  /// Glyph override (a block's call to action).
  final IconData? icon;

  /// Controls after the glyph (retry, dismiss), each icon-only.
  final List<Widget> trailing;

  @override
  State<CueChip> createState() => _CueChipState();
}

class _CueChipState extends State<CueChip> with SingleTickerProviderStateMixin {
  late final AnimationController _shake = AnimationController(
    vsync: this,
    duration: AppDuration.slow,
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _maybeShake();
  }

  @override
  void didUpdateWidget(CueChip old) {
    super.didUpdateWidget(old);
    if (old.semanticLabel != widget.semanticLabel || old.kind != widget.kind) {
      _maybeShake();
    }
  }

  void _maybeShake() {
    if (widget.kind != CueKind.error) return;
    if (MediaQuery.maybeDisableAnimationsOf(context) ?? false) return;
    _shake.forward(from: 0);
  }

  @override
  void dispose() {
    _shake.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final color = cueColor(context, widget.kind);
    final glyph = widget.kind == CueKind.pending && widget.icon == null
        ? SizedBox.square(
            dimension: AppSpacing.md + 2,
            child: CircularProgressIndicator(strokeWidth: 2, color: color),
          )
        : Icon(widget.icon ?? cueIcon(widget.kind), color: color);
    final chip = Container(
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
      child: glyph,
    );
    return AnimatedBuilder(
      animation: _shake,
      builder: (context, child) => Transform.translate(
        // Three damped swings; still at 0 and 1.
        offset: Offset(
          math.sin(_shake.value * math.pi * 6) * 6 * (1 - _shake.value),
          0,
        ),
        child: child,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          SpokenLabel(
            semanticLabel: widget.semanticLabel,
            liveRegion: true,
            child: chip,
          ),
          ...widget.trailing,
        ],
      ),
    );
  }
}
