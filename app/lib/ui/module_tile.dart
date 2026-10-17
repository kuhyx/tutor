/// One module of an approved plan on the Plan screen.
library;

import 'package:flutter/material.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/progress/terms.dart';
import 'package:tutor/ui/card_state.dart';

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

  @override
  Widget build(BuildContext context) {
    final m = module;
    final failed = m.status == ModuleStatus.failed;
    final reviewable =
        review == ModuleReview.done && m.status != ModuleStatus.mastered;
    final badge = moduleBadge(m, review);
    final counted = tally != null && tally!.cards > 0;
    final help = [?badgeHelp(badge), if (counted) tallyHelp].join('\n');
    final subtitle = Text(
      [
        badge,
        if (m.cards > 0) '${m.cards} cards',
        if (counted) tally!.doneText,
        'recall ${(m.recall * 100).round()}%',
        if (failed && m.error != null) m.error!,
      ].join(' · '),
    );
    return Card(
      child: ListTile(
        title: Text(m.title),
        subtitle: Explained(help, child: subtitle),
        trailing: failed
            ? TextButton(onPressed: onRetry, child: const Text('Retry'))
            : reviewable && onReview != null
            ? FilledButton.tonal(
                onPressed: onReview,
                child: const Text('Review this module'),
              )
            : null,
      ),
    );
  }
}
