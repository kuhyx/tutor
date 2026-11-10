/// Small rounded labels: a painted [Pill] (content or digits) and the
/// glyph [GlyphPill] (textgate: old wording spoken only).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// A small rounded label. Its [text] is painted: pass content or digits
/// only (use [GlyphPill] for app wording).
class Pill extends StatelessWidget {
  /// Creates the pill; [warn] uses the warning fill.
  const new(this.text, {this.warn = false, super.key});

  /// Label.
  final String text;

  /// Warning colour instead of the muted surface.
  final bool warn;

  @override
  Widget build(BuildContext context) => _PillShell(
    warn: warn,
    child: Text(
      text,
      style: TextStyle(
        fontSize: AppTextSize.caption,
        color: warn ? AppPalette.onFill : null,
      ),
    ),
  );
}

/// A pill that is a glyph (plus an optional number): the old wording is
/// spoken only (paused, stalled, stopped, archived, PC offline...).
class GlyphPill extends StatelessWidget {
  /// Creates the pill.
  const new({
    required this.icon,
    required this.semanticLabel,
    this.value,
    this.warn = false,
    super.key,
  });

  /// The glyph.
  final IconData icon;

  /// The old wording, spoken only.
  final String semanticLabel;

  /// A number shown next to the glyph; null = none.
  final String? value;

  /// Warning colour instead of the muted surface.
  final bool warn;

  @override
  Widget build(BuildContext context) {
    final color = warn
        ? AppPalette.onFill
        : Theme.of(context).colorScheme.onSurface;
    return SpokenLabel(
      semanticLabel: semanticLabel,
      child: _PillShell(
        warn: warn,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: AppTextSize.label, color: color),
            if (value != null) ...[
              const SizedBox(width: AppSpacing.xs),
              Text(
                value!,
                style: TextStyle(fontSize: AppTextSize.caption, color: color),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _PillShell extends StatelessWidget {
  const new({required this.warn, required this.child});

  final bool warn;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    // Sized to its content even where a list stretches its children.
    return Align(
      alignment: AlignmentDirectional.centerStart,
      widthFactor: 1,
      heightFactor: 1,
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.sm,
          vertical: AppSpacing.xs,
        ),
        decoration: BoxDecoration(
          color: warn ? AppPalette.warning : scheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(AppRadius.lg),
        ),
        child: DefaultTextStyle.merge(
          style: TextStyle(color: warn ? AppPalette.onFill : scheme.onSurface),
          child: child,
        ),
      ),
    );
  }
}
