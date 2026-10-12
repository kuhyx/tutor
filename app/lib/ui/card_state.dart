/// The cards view's progress marks: a subject summary with a bar, and a
/// per-card icon (mastered / done / not taught yet), as the retired page's
/// deck summary and done marks showed them.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/progress/card_progress.dart';

/// "x/y done · z mastered · n due" with a done bar.
class ProgressSummary extends StatelessWidget {
  /// Creates the summary.
  const new(this.tally, {super.key});

  /// The subject's counts.
  final Tally tally;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(tally.summary, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: AppSpacing.sm),
          LinearProgressIndicator(value: tally.taught / tally.cards),
        ],
      ),
    ),
  );
}

/// A card's state as an icon with a tooltip (null: not folded yet).
class CardStateIcon extends StatelessWidget {
  /// Creates the icon.
  const new(this.progress, {super.key});

  /// The card's state.
  final CardProgress? progress;

  @override
  Widget build(BuildContext context) {
    final p = progress;
    final scheme = Theme.of(context).colorScheme;
    final (icon, color) = switch (p) {
      null => (Icons.circle_outlined, scheme.outline),
      CardProgress(mastered: true) => (Icons.star, scheme.primary),
      CardProgress(taught: true) => (Icons.check_circle, scheme.primary),
      _ => (Icons.radio_button_unchecked, scheme.outline),
    };
    return Tooltip(
      message: p?.label ?? '',
      child: Icon(icon, color: color),
    );
  }
}
