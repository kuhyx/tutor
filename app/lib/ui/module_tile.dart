/// One module of an approved plan on the Plan screen.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/progress/terms.dart';
import 'package:tutor/ui/card_state.dart';
import 'package:tutor/ui/code_glyphs.dart';
import 'package:tutor/ui/learn_bits.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// An approved plan's module: status, card count, recall; Retry if failed;
/// "Review this module" once every card is done but not yet reviewed.
class ModuleProgressTile extends StatelessWidget {
  /// Creates the tile.
  const new({
    required this.module,
    required this.onRetry,
    this.tally,
    this.review,
    this.onReview,
    this.onReviewDue,
    super.key,
  });

  /// The module.
  final Module module;

  /// Its cards: done / recalled / due (null until the log is folded).
  final Tally? tally;

  /// Its review state (null until the log is folded).
  final ModuleReview? review;

  /// Asks the worker to try generating again.
  final VoidCallback onRetry;

  /// Starts the module review.
  final VoidCallback? onReview;

  /// Reviews only the module's due cards (a button while [tally] has some).
  final VoidCallback? onReviewDue;

  @override
  Widget build(BuildContext context) {
    final m = module;
    final failed = m.status == ModuleStatus.failed;
    final reviewable =
        review == ModuleReview.done && m.status != ModuleStatus.mastered;
    final mark = moduleMark(m, review);
    final badge = mark.name;
    final counted = tally != null && tally!.cards > 0;
    final help = [?badgeHelp(badge), if (counted) tallyHelp].join('\n');
    // The old status line is the spoken label; the marks are glyphs.
    final subtitle = SpokenLabel(
      // The lock glyph's word too: this label replaces its children's.
      semanticLabel: [
        badge,
        if (!m.teachable) teachLockLabel,
        if (m.cards > 0) '${m.cards} cards',
        if (counted) tally!.doneText,
        'recall ${(m.recall * 100).round()}%',
        if (failed && m.error != null) m.error!,
      ].join(' · '),
      child: Wrap(
        spacing: AppSpacing.md,
        runSpacing: AppSpacing.xs,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          if (!m.teachable) const TeachLock(),
          if (m.cards > 0) GlyphStat(Icons.style_outlined, '${m.cards}'),
          if (counted) TallyRow(tally!),
          RecallStat(m.recall),
          if (failed && m.error != null)
            Icon(
              errorKindIcon(m.errorKind),
              color: Theme.of(context).colorScheme.error,
            ),
        ],
      ),
    );
    final due = tally?.due ?? 0;
    final replay = reviewable && onReview != null
        ? GlyphButton(
            icon: Icons.replay,
            semanticLabel: 'Review this module',
            tooltip: (l) => l.tooltip_review,
            filled: true,
            onPressed: onReview,
          )
        : null;
    final dueButton = due > 0 && onReviewDue != null
        ? ModuleDueButton(m, due, onPressed: onReviewDue)
        : null;
    return Card(
      child: ListTile(
        leading: ModuleMarkIcon(mark),
        title: ContentText(m.title),
        subtitle: Explained(help, child: subtitle),
        trailing: failed
            ? GlyphButton(
                icon: Icons.refresh,
                semanticLabel: 'Retry',
                tooltip: (l) => l.tooltip_retry,
                tint: Theme.of(context).colorScheme.error,
                onPressed: onRetry,
              )
            : dueButton == null
            ? replay
            : Row(
                mainAxisSize: MainAxisSize.min,
                children: [dueButton, ?replay],
              ),
      ),
    );
  }
}

/// A module's due-only review: the card glyph with its [due] count.
class ModuleDueButton extends StatelessWidget {
  /// Creates the button for [module].
  const new(
    this.module,
    this.due, {
    required this.onPressed,
    this.target,
    super.key,
  });

  /// The module.
  final Module module;

  /// Its due cards.
  final int due;

  /// Runs them.
  final VoidCallback? onPressed;

  /// A dense tap target (dp) for a phone tile; null = the theme's.
  final double? target;

  @override
  Widget build(BuildContext context) => GlyphButton(
    icon: Icons.style,
    semanticLabel: 'Review ${module.title} ($due due)',
    count: due,
    tint: AppPalette.danger,
    target: target,
    tooltip: (l) => l.tooltip_review,
    onPressed: onPressed,
  );
}
