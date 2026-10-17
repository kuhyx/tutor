/// One subject on Home: status, modules reviewed, and its actions (Plan,
/// Cards, Learn this next, "Review" + a done module, Go deeper / Review
/// only).
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
    this.onReviewModule,
    super.key,
  });

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
    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ListTile(
            leading: Icon(
              current ? Icons.radio_button_checked : Icons.radio_button_off,
            ),
            title: Text(entry.meta.title),
            subtitle: Explained(
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
