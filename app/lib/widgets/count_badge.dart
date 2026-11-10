/// Numbers instead of sentences: a count badge, a glyph + number stat and
/// the session id chip.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/widgets/content_text.dart';

/// A rounded number ("3" due, "12" days left).
class CountBadge extends StatelessWidget {
  /// Creates the badge.
  const new(this.count, {this.color, this.icon, super.key});

  /// Places a small badge with [count] on [child]'s top end.
  static Widget on(Widget child, {required int count, Color? color}) => Badge(
    label: Text('$count'),
    backgroundColor: color,
    isLabelVisible: count > 0,
    child: child,
  );

  /// The number.
  final int count;

  /// Fill; null = the theme's secondary container.
  final Color? color;

  /// A leading glyph naming what is counted; null = the number alone.
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final fill = color ?? scheme.secondaryContainer;
    final ink = color == null ? scheme.onSecondaryContainer : AppPalette.onFill;
    final glyph = icon;
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs / 2,
      ),
      decoration: BoxDecoration(
        color: fill,
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (glyph != null) ...[
            Icon(glyph, size: AppTextSize.label, color: ink),
            const SizedBox(width: AppSpacing.xs),
          ],
          Text(
            '$count',
            style: TextStyle(fontSize: AppTextSize.caption, color: ink),
          ),
        ],
      ),
    );
  }
}

/// A stat: [icon] plus a [value] (digits, a ratio, a date).
class GlyphStat extends StatelessWidget {
  /// Creates the stat.
  const new(this.icon, this.value, {this.color, this.size, super.key});

  /// What is measured.
  final IconData icon;

  /// The number, already formatted (no words).
  final String value;

  /// Tint for icon and number; null = the theme's.
  final Color? color;

  /// Number size; null = body.
  final double? size;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(icon, size: (size ?? AppTextSize.body) + 2, color: color),
      const SizedBox(width: AppSpacing.xs),
      // Shrinks (never overflows) in a narrow cell.
      Flexible(
        child: Text(
          value,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            fontSize: size ?? AppTextSize.body,
            color: color,
            fontFeatures: const [FontFeature.tabularFigures()],
          ),
        ),
      ),
    ],
  );
}

/// A session id as a short monospaced chip (content: it names the session).
class IdChip extends StatelessWidget {
  /// Creates the chip for [id].
  const new(this.id, {super.key});

  /// The full session id.
  final String id;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(
      horizontal: AppSpacing.sm,
      vertical: AppSpacing.xs / 2,
    ),
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      borderRadius: BorderRadius.circular(AppRadius.sm),
    ),
    child: ContentText(
      id.length > 4 ? id.substring(id.length - 4) : id,
      style: const TextStyle(
        fontFamily: 'monospace',
        fontSize: AppTextSize.caption,
      ),
    ),
  );
}
