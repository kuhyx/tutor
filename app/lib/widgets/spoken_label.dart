/// Icon-only controls (textgate): the old wording lives on only as the
/// spoken label (screen readers, the browser drivers' aria-label), never
/// painted and never a tooltip (a tooltip paints on long-press).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/widgets/count_badge.dart';

/// Gives [child] exactly [semanticLabel] as its spoken label; its own
/// semantics (an icon's, a badge's number) are folded into it.
class SpokenLabel extends StatelessWidget {
  /// Creates the label.
  const new({
    required this.semanticLabel,
    required this.child,
    this.button = false,
    this.enabled,
    this.onTap,
    this.liveRegion = false,
    this.expanded,
    super.key,
  });

  /// What a screen reader says.
  final String semanticLabel;

  /// The painted part.
  final Widget child;

  /// Announced as a button.
  final bool button;

  /// Enabled state for a [button]; null = not stated.
  final bool? enabled;

  /// The semantic tap, for a [button] whose own action is folded away.
  final VoidCallback? onTap;

  /// Announced when it changes (status cues).
  final bool liveRegion;

  /// Expanded state of a folding header; null = not stated.
  final bool? expanded;

  @override
  Widget build(BuildContext context) => Semantics(
    // A button is its own node: inside a Card (a merging semantic
    // container) it would otherwise fold into the card's label and the
    // drivers could not find or tap it.
    container: button,
    label: semanticLabel,
    button: button,
    enabled: enabled,
    onTap: onTap,
    liveRegion: liveRegion,
    expanded: expanded,
    excludeSemantics: true,
    child: child,
  );
}

/// An icon button with a spoken label, an optional count badge and tint;
/// [filled] for the screen's primary action.
class GlyphButton extends StatelessWidget {
  /// Creates the button.
  const new({
    required this.icon,
    required this.semanticLabel,
    required this.onPressed,
    this.count,
    this.tint,
    this.filled = false,
    this.selected = false,
    this.size,
    super.key,
  });

  /// The glyph.
  final IconData icon;

  /// The old wording, spoken only.
  final String semanticLabel;

  /// Tap; null = disabled.
  final VoidCallback? onPressed;

  /// A number shown as a badge on the glyph (due cards, ...); null = none.
  final int? count;

  /// Glyph colour; null = the theme's.
  final Color? tint;

  /// Filled (primary) instead of plain.
  final bool filled;

  /// Shown selected (a toggle that is on).
  final bool selected;

  /// Glyph size; null = the theme's.
  final double? size;

  @override
  Widget build(BuildContext context) {
    final n = count;
    Widget glyph = Icon(icon, color: filled ? null : tint, size: size);
    if (n != null) glyph = CountBadge.on(glyph, count: n, color: tint);
    final button = filled
        ? IconButton.filled(
            onPressed: onPressed,
            isSelected: selected,
            style: tint == null
                ? null
                : IconButton.styleFrom(backgroundColor: tint),
            icon: glyph,
          )
        : IconButton(
            onPressed: onPressed,
            isSelected: selected,
            constraints: const BoxConstraints(
              minWidth: AppSpacing.xxl,
              minHeight: AppSpacing.xxl,
            ),
            icon: glyph,
          );
    return SpokenLabel(
      semanticLabel: semanticLabel,
      button: true,
      enabled: onPressed != null,
      onTap: onPressed,
      child: button,
    );
  }
}
