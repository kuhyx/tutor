/// One subject on Home: status, modules reviewed, and its actions as glyph
/// buttons (Plan, Cards, Learn this next, Review a done module, Review with
/// the subject's due count, Try again, Go deeper / Review only).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/home/home_loader.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/progress/progress.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/spoken_label.dart';
import 'package:tutor/widgets/status_glyph.dart';

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
    final scheme = Theme.of(context).colorScheme;
    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ListTile(
            leading: Icon(
              current ? Icons.radio_button_checked : Icons.radio_button_off,
              semanticLabel: current ? 'New material from here' : null,
            ),
            title: ContentText(entry.meta.title),
            subtitle: Wrap(
              spacing: AppSpacing.md,
              runSpacing: AppSpacing.xs,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                StatusGlyph(
                  status,
                  detail: entry.meta.error,
                  errorKind: entry.meta.errorKind,
                ),
                // Modules reviewed, and per card a separate stat.
                if (total > 0)
                  SpokenLabel(
                    semanticLabel: '$reviewed/$total modules reviewed',
                    child: GlyphStat(
                      Icons.view_module_outlined,
                      '$reviewed/$total',
                    ),
                  ),
                if (cards != null && cards.cards > 0)
                  SpokenLabel(
                    semanticLabel:
                        '${cards.mastered}/${cards.cards} cards recalled',
                    child: GlyphStat(
                      Icons.psychology_alt_outlined,
                      '${cards.mastered}/${cards.cards}',
                      color: scheme.primary,
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
                  GlyphButton(
                    icon: Icons.fact_check_outlined,
                    semanticLabel: 'Review ${review.title}',
                    tint: AppPalette.success,
                    onPressed: () => onReviewModule!(review),
                  ),
                if (due > 0 && onReviewDue != null)
                  GlyphButton(
                    icon: Icons.style,
                    semanticLabel: 'Review ($due due)',
                    count: due,
                    tint: scheme.primary,
                    onPressed: onReviewDue,
                  ),
                GlyphButton(
                  icon: Icons.account_tree_outlined,
                  semanticLabel: 'Plan',
                  onPressed: onPlan,
                ),
                if (data != null && data.cards.isNotEmpty)
                  GlyphButton(
                    icon: Icons.view_carousel_outlined,
                    semanticLabel: 'Cards',
                    onPressed: onEdit,
                  ),
                if (teaching && !current)
                  GlyphButton(
                    icon: Icons.arrow_circle_right_outlined,
                    semanticLabel: 'Learn this next',
                    tint: scheme.primary,
                    onPressed: onPick,
                  ),
                if (status == SubjectStatus.failed &&
                    entry.meta.goal.isNotEmpty)
                  GlyphButton(
                    icon: Icons.restart_alt,
                    semanticLabel: 'Try again',
                    tint: scheme.error,
                    onPressed: onRetry,
                  ),
                if (status == SubjectStatus.completed) ...[
                  GlyphButton(
                    icon: Icons.keyboard_double_arrow_down,
                    semanticLabel: 'Go deeper',
                    tint: AppPalette.warning,
                    onPressed: () => onFinish(true),
                  ),
                  GlyphButton(
                    icon: Icons.replay,
                    semanticLabel: 'Review only',
                    tint: AppPalette.success,
                    onPressed: () => onFinish(false),
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
