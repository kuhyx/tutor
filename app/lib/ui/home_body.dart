/// Home's content: today's counters, review and session entry points,
/// subjects, and the new-subject field (glyphs and numbers, no words).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/home/home_loader.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/session/session_entry.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/fit_parts.dart';
import 'package:tutor/ui/home_fit.dart';
import 'package:tutor/ui/layout.dart';
import 'package:tutor/ui/new_subject_field.dart';
import 'package:tutor/ui/subject_tile.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// Home's body.
class HomeBody extends StatelessWidget {
  /// Creates the body.
  const new({
    required this.data,
    required this.presence,
    required this.runner,
    required this.onReview,
    required this.onDrill,
    required this.onSession,
    required this.onPlan,
    required this.onEdit,
    required this.onPick,
    required this.onNewSubject,
    required this.onFinish,
    this.onReviewModule,
    this.onReviewSubject,
    super.key,
  });

  /// Reviews one subject's due cards (id, title).
  final void Function(String subject, String title)? onReviewSubject;

  /// Starts a done module's review.
  final ValueChanged<ModuleRef>? onReviewModule;

  /// Snapshot.
  final HomeSnapshot data;

  /// PC presence.
  final ValueNotifier<PcPresence> presence;

  /// Runs subject requests.
  final RequestRunner runner;

  /// Opens Review.
  final VoidCallback onReview;

  /// Opens Review in Drill mode (pick-an-answer, no model).
  final VoidCallback onDrill;

  /// Opens the Session for Home's button.
  final ValueChanged<SessionEntry> onSession;

  /// Opens a subject's plan.
  final ValueChanged<String> onPlan;

  /// Opens a subject's cards.
  final ValueChanged<String> onEdit;

  /// Picks the subject new material comes from.
  final ValueChanged<String> onPick;

  /// Sends "I want to learn...".
  final ValueChanged<String> onNewSubject;

  /// Completed subject: go deeper or review only.
  final void Function(String subject, {required bool goDeeper}) onFinish;

  @override
  Widget build(BuildContext context) {
    final today = data.today;
    final entry = sessionEntry(data.live, data.currentSubject);
    final scheme = Theme.of(context).colorScheme;
    // Wide: today on the left; subjects and a new one on the right.
    final first = <Widget>[
      if (data.offline)
        const Padding(
          padding: EdgeInsets.only(bottom: AppSpacing.sm),
          child: CueChip(
            kind: CueKind.offline,
            semanticLabel: 'Offline: showing the last synced catalog',
          ),
        ),
      PcOfflineBanner(presence),
      Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (today == null)
                const Icon(
                  Icons.timer_off_outlined,
                  semanticLabel: 'No counters yet (the PC writes them).',
                )
              else ...[
                _counters(today, scheme),
                const SizedBox(height: AppSpacing.sm),
                LinearProgressIndicator(
                  value: today.target == 0
                      ? 0
                      : (today.creditedMinutes / today.target).clamp(0, 1),
                ),
              ],
              const SizedBox(height: AppSpacing.md),
              Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.sm,
                children: [
                  GlyphButton(
                    icon: switch (entry.kind) {
                      SessionKind.learn => Icons.school_outlined,
                      SessionKind.live => Icons.chat_bubble_outline,
                      SessionKind.resume => Icons.play_circle_outline,
                    },
                    semanticLabel: entry.semanticLabel,
                    filled: true,
                    onPressed: () => onSession(entry),
                  ),
                  // Every subject's due cards. Nothing due: no button (kuhy,
                  // 2026-10-17).
                  if (data.due > 0)
                    GlyphButton(
                      icon: Icons.style,
                      semanticLabel: 'Review (${data.due} due)',
                      count: data.due,
                      tint: scheme.primary,
                      onPressed: onReview,
                    ),
                  GlyphButton(
                    icon: Icons.touch_app_outlined,
                    semanticLabel: 'Drill',
                    tint: AppPalette.warning,
                    onPressed: onDrill,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    ];
    final second = <Widget>[
      if (data.subjects.isEmpty)
        const Padding(
          padding: EdgeInsets.all(AppSpacing.lg),
          child: Icon(
            Icons.lightbulb_outline,
            size: 64,
            semanticLabel: 'No subjects yet. Say what you want to learn below.',
          ),
        ),
      for (final s in data.subjects)
        SubjectTile(
          entry: s,
          toReview: data.toReview[s.id],
          tally: data.cardTally[s.id],
          due: data.dueBySubject[s.id] ?? 0,
          onReviewModule: onReviewModule,
          onReviewDue: onReviewSubject == null
              ? null
              : () => onReviewSubject!(s.id, s.meta.title),
          current: s.id == data.currentSubject,
          onPlan: () => onPlan(s.id),
          onEdit: () => onEdit(s.id),
          onPick: () => onPick(s.id),
          onFinish: (goDeeper) => onFinish(s.id, goDeeper: goDeeper),
          onRetry: () => onNewSubject(s.meta.goal),
        ),
      const Divider(height: AppSpacing.xl),
      NewSubjectField(runner: runner, onSubmit: onNewSubject),
    ];
    return widthSwitch(
      narrow: (_) => HomeFit(body: this, today: first),
      wide: (_) => TwoColumnPage(
        secondFlex: 3,
        firstFlex: 2,
        first: first,
        second: second,
      ),
    );
  }
}

/// Today's counters as glyph + number: credited/target minutes, active
/// minutes, new cards/limit (a lock-open mark when lifted), the bank.
Widget _counters(Today today, ColorScheme scheme) {
  final banked = today.banked ?? 0;
  final prepaid = today.prepaid ?? 0;
  final active = today.activeMinutes;
  return Wrap(
    spacing: AppSpacing.md,
    runSpacing: AppSpacing.xs,
    crossAxisAlignment: WrapCrossAlignment.center,
    children: [
      SpokenLabel(
        semanticLabel: 'Credited ${today.creditedMinutes}/${today.target} min',
        child: GlyphStat(
          Icons.verified_outlined,
          '${today.creditedMinutes}/${today.target}',
          color: scheme.primary,
        ),
      ),
      if (active != null)
        SpokenLabel(
          semanticLabel: '$active min active',
          child: GlyphStat(Icons.timer_outlined, '$active'),
        ),
      SpokenLabel(
        semanticLabel: 'new cards ${today.newCards}/${today.newCap}',
        child: GlyphStat(Icons.add_card, '${today.newCards}/${today.newCap}'),
      ),
      if (today.newCapLifted)
        const Icon(Icons.lock_open, semanticLabel: '(limit lifted)'),
      if (banked > 0 || prepaid > 0)
        SpokenLabel(
          semanticLabel: 'Banked $banked min · prepaid $prepaid',
          child: GlyphStat(Icons.savings_outlined, '$banked · $prepaid'),
        ),
    ],
  );
}
