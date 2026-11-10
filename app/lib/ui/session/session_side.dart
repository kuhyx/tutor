/// The Session's side panel (`index.html` aside): target card, Switch card,
/// Mark card done, Stop here, Edit cards, Report a problem, known concepts.
/// Text-free: glyph buttons (the old wording is their spoken label); the
/// subject, card and concept names are content.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// Side panel.
class SessionSide extends StatelessWidget {
  /// Creates the panel.
  const new({
    required this.meta,
    required this.subject,
    required this.mastered,
    required this.onSwitch,
    required this.onMarkDone,
    required this.onStop,
    required this.onEdit,
    required this.onReport,
    required this.onHistory,
    super.key,
  });

  /// Session meta (null before it arrives).
  final SessionMeta? meta;

  /// The session's subject, when cached.
  final SubjectData? subject;

  /// Known concept names (the wire's `mastered`), oldest first.
  final List<String> mastered;

  /// Start another card instead.
  final VoidCallback? onSwitch;

  /// Count the live card as done.
  final VoidCallback? onMarkDone;

  /// End the live session before its card is done (old page's Stop here).
  final VoidCallback? onStop;

  /// Open the card editor.
  final VoidCallback onEdit;

  /// Report a problem with the whole experience.
  final VoidCallback onReport;

  /// Open History.
  final VoidCallback onHistory;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final m = meta;
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.md),
      children: [
        if (subject != null) ...[
          ContentText(subject!.meta.title, style: text.titleMedium),
          const SizedBox(height: AppSpacing.md),
        ],
        Row(
          children: [
            const SpokenLabel(
              semanticLabel: 'Target card',
              child: Icon(Icons.gps_fixed, size: AppTextSize.body),
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(child: ContentText(m?.card?.front ?? '-')),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            GlyphButton(
              icon: Icons.swap_horiz,
              semanticLabel: 'Switch card',
              onPressed: onSwitch,
            ),
            GlyphButton(
              icon: Icons.task_alt,
              semanticLabel: 'Mark card done',
              tint: AppPalette.success,
              onPressed: onMarkDone,
            ),
            GlyphButton(
              icon: Icons.stop_circle_outlined,
              semanticLabel: 'Stop here',
              onPressed: onStop,
            ),
            GlyphButton(
              icon: Icons.edit_note,
              semanticLabel: 'Edit cards',
              onPressed: onEdit,
            ),
            GlyphButton(
              icon: Icons.history,
              semanticLabel: 'History',
              onPressed: onHistory,
            ),
            GlyphButton(
              icon: Icons.flag_outlined,
              semanticLabel: 'Report a problem',
              onPressed: onReport,
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.lg),
        // Known concepts: a glyph, the count, the names (content).
        SpokenLabel(
          semanticLabel: 'Known',
          child: GlyphStat(Icons.lightbulb_outline, '${mastered.length}'),
        ),
        const SizedBox(height: AppSpacing.xs),
        for (final c in mastered.reversed) ContentText('• $c'),
      ],
    );
  }
}

/// Picks a card of [subject] to start a session on (module order, then
/// card order). Null when dismissed.
Future<String?> pickCard(BuildContext context, SubjectData subject) =>
    showDialog<String>(
      context: context,
      builder: (context) => SimpleDialog(
        children: [
          for (final m in subject.plan?.modules ?? const <Module>[])
            for (final e in subject.cardsOf(m.id))
              SimpleDialogOption(
                onPressed: () => Navigator.pop(context, e.key),
                child: ContentText('${m.title}: ${e.value.front}'),
              ),
        ],
      ),
    );
