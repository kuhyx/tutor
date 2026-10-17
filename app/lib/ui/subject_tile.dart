/// One subject on Home: status, modules reviewed, and its actions (Plan,
/// Cards, Learn this next, "Review" + a done module, "Review (N due)" for
/// this subject's due cards only, Go deeper / Review only).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/home/home_loader.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/progress/progress.dart';
import 'package:tutor/progress/terms.dart';
import 'package:tutor/ui/card_state.dart';

/// A subject's card on Home.
class SubjectTile extends StatelessWidget {
  /// Creates the tile.
  const new({
    required this.entry,
    required this.current,
    required this.onPlan,
    required this.onEdit,
    required this.onPick,
    required this.onFinish,
    required this.onRetry,
    this.toReview,
    this.tally,
    this.onReviewModule,
    this.due = 0,
    this.onReviewDue,
    super.key,
  });

  /// This subject's cards due now.
  final int due;

  /// Reviews only this subject's due cards (shown while [due] > 0).
  final VoidCallback? onReviewDue;

  /// The subject.
  final SubjectEntry entry;

  /// New material comes from here.
  final bool current;

  /// Opens the plan.
  final VoidCallback onPlan;

  /// Opens the cards.
  final VoidCallback onEdit;

  /// Makes it the current subject.
  final VoidCallback onPick;

  /// Completed: go deeper (true) or review only.
  final ValueChanged<bool> onFinish;

  /// Failed: drafts the plan again.
  final VoidCallback onRetry;

  /// The subject's cards (recalled / total), when folded.
  final Tally? tally;

  /// A done module waiting for its review.
  final ModuleRef? toReview;

  /// Starts that module's review.
  final ValueChanged<ModuleRef>? onReviewModule;

  @override
  Widget build(BuildContext context) {
    final status = entry.meta.status;
    final data = entry.data;
    // `mastered` on the wire is what the app calls "reviewed".
    final (reviewed, total) = data == null ? (0, 0) : masteredOf(data);
    final teaching =
        status == SubjectStatus.active || status == SubjectStatus.completed;
    final review = toReview;
    final cards = tally;
    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ListTile(
            leading: Icon(
              current ? Icons.radio_button_checked : Icons.radio_button_off,
            ),
            title: Text(entry.meta.title),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Explained(
                  total > 0 ? reviewedModuleHelp : null,
                  child: Text(
                    [
                      status.wire.replaceAll('_', ' '),
                      if (total > 0) '$reviewed/$total modules reviewed',
                      if (current) 'new material from here',
                      ?entry.meta.error,
                    ].join(' · '),
                  ),
                ),
                // Per card, a separate stat from the module count above.
                if (cards != null && cards.cards > 0)
                  Explained(
                    recalledHelp,
                    child: Text(
                      '${cards.mastered}/${cards.cards} cards recalled',
                    ),
                  ),
              ],
            ),
            onTap: teaching && !current ? onPick : onPlan,
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.md,
              0,
              AppSpacing.md,
              AppSpacing.sm,
            ),
            child: Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                if (review != null && onReviewModule != null)
                  FilledButton.tonalIcon(
                    onPressed: () => onReviewModule!(review),
                    icon: const Icon(Icons.style),
                    label: Text('Review ${review.title}'),
                  ),
                if (due > 0 && onReviewDue != null)
                  OutlinedButton.icon(
                    onPressed: onReviewDue,
                    icon: const Icon(Icons.style),
                    label: Text('Review ($due due)'),
                  ),
                TextButton(onPressed: onPlan, child: const Text('Plan')),
                if (data != null && data.cards.isNotEmpty)
                  TextButton(onPressed: onEdit, child: const Text('Cards')),
                if (teaching && !current)
                  TextButton(
                    onPressed: onPick,
                    child: const Text('Learn this next'),
                  ),
                if (status == SubjectStatus.failed &&
                    entry.meta.goal.isNotEmpty)
                  TextButton(
                    onPressed: onRetry,
                    child: const Text('Try again'),
                  ),
                if (status == SubjectStatus.completed) ...[
                  TextButton(
                    onPressed: () => onFinish(true),
                    child: const Text('Go deeper'),
                  ),
                  TextButton(
                    onPressed: () => onFinish(false),
                    child: const Text('Review only'),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
