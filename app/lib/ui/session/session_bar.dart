/// The Session screen's card actions (Switch card, Mark card done, Stop
/// here, Edit cards, History, Report a problem) and, on a wide desktop
/// window, the top bar that holds them with the title and the day's stats,
/// the narrow card pane beside the chat and the Known dialog (kuhy,
/// 2026-11-22). Glyphs only; the old wording is the spoken label.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// From this window width the stats share the title's line.
const kBarOneLine = 1400.0;

/// The wide desktop card pane's width.
const kCardPaneWidth = 300.0;

/// The bar's height with the stats on a second line.
const double kBarTwoLineHeight = kToolbarHeight + 32;

/// The height of the line under the bar that holds a phone's LeetCode stats.
const double kBarRowHeight = AppSpacing.xl + AppSpacing.sm;

/// What the card action glyphs do; a null callback greys its glyph.
class CardActions {
  /// Creates the set.
  const new({
    required this.onSwitch,
    required this.onMarkDone,
    required this.onStop,
    required this.onEdit,
    required this.onHistory,
    required this.onReport,
  });

  /// Start another card instead.
  final VoidCallback? onSwitch;

  /// Count the live card as done.
  final VoidCallback? onMarkDone;

  /// End the live session before its card is done (old page's Stop here).
  final VoidCallback? onStop;

  /// Open the card editor.
  final VoidCallback onEdit;

  /// Open History.
  final VoidCallback onHistory;

  /// Report a problem with the whole experience.
  final VoidCallback onReport;

  /// The glyphs, in the bar's (and the drawer's) order.
  List<Widget> glyphs() => [
    GlyphButton(
      icon: Icons.swap_horiz,
      semanticLabel: 'Switch card',
      tooltip: (l) => l.tooltip_switch,
      onPressed: onSwitch,
    ),
    GlyphButton(
      icon: Icons.task_alt,
      semanticLabel: 'Mark card done',
      tint: AppPalette.success,
      tooltip: (l) => l.tooltip_complete,
      onPressed: onMarkDone,
    ),
    GlyphButton(
      icon: Icons.stop_circle_outlined,
      semanticLabel: 'Stop here',
      tooltip: (l) => l.tooltip_stop,
      onPressed: onStop,
    ),
    GlyphButton(
      icon: Icons.edit_note,
      semanticLabel: 'Edit cards',
      tooltip: (l) => l.tooltip_edit,
      onPressed: onEdit,
    ),
    GlyphButton(
      icon: Icons.history,
      semanticLabel: 'History',
      tooltip: (l) => l.tooltip_history,
      onPressed: onHistory,
    ),
    GlyphButton(
      icon: Icons.flag_outlined,
      semanticLabel: 'Report a problem',
      tooltip: (l) => l.tooltip_report,
      onPressed: onReport,
    ),
  ];
}

/// The bar's title: the subject's name, then the day's [stats] on the same
/// line, or under it when [twoLines]. The name shortens first.
class BarTitle extends StatelessWidget {
  /// Creates the title.
  const new({
    required this.title,
    required this.stats,
    required this.twoLines,
    this.lead,
    this.spoken,
    super.key,
  });

  /// The subject's name (content), or a lesson's unit; null before it loads.
  final String? title;

  /// A glyph before the [title] (the pencil of a LeetCode unit).
  final IconData? lead;

  /// What a screen reader says for the [lead] and [title] together.
  final String? spoken;

  /// The stats and marks; null before the session loads.
  final Widget? stats;

  /// The stats sit on a second line.
  final bool twoLines;

  @override
  Widget build(BuildContext context) {
    final text = title == null
        ? const SizedBox.shrink()
        : ContentText(title!, maxLines: 1, overflow: TextOverflow.ellipsis);
    final glyph = lead;
    final say = spoken;
    final name = glyph == null
        ? text
        : SpokenLabel(
            semanticLabel: say ?? title ?? '',
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(glyph),
                const SizedBox(width: AppSpacing.sm),
                Flexible(child: text),
              ],
            ),
          );
    final s = stats;
    if (s == null) return name;
    return twoLines
        ? Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [name, s],
          )
        : Row(
            children: [
              Flexible(child: name),
              const SizedBox(width: AppSpacing.lg),
              s,
            ],
          );
  }
}

/// The wide desktop pane: only the target card's front.
class SessionCardPane extends StatelessWidget {
  /// Creates the pane for [meta] (null before it arrives).
  const new({required this.meta, super.key});

  /// Session meta.
  final SessionMeta? meta;

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(AppSpacing.md),
    children: [
      Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SpokenLabel(
            semanticLabel: 'Target card',
            child: Icon(Icons.gps_fixed, size: AppTextSize.body),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(child: ContentText(meta?.card?.front ?? '-')),
        ],
      ),
    ],
  );
}

/// The bar's Known glyph: opens [showKnown] for [mastered].
Widget knownGlyph(List<String> mastered) => Builder(
  builder: (context) => GlyphButton(
    icon: Icons.checklist,
    semanticLabel: 'Known',
    tooltip: (l) => l.tooltip_known,
    onPressed: () => showKnown(context, mastered),
  ),
);

/// The known concepts ([mastered], oldest first) as a dialog: the count
/// under a glyph, then the names, newest first.
Future<void> showKnown(BuildContext context, List<String> mastered) =>
    showDialog<void>(
      context: context,
      builder: (context) => Dialog(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                knownCount(mastered),
                const SizedBox(height: AppSpacing.sm),
                Flexible(
                  child: ListView(
                    shrinkWrap: true,
                    children: [
                      for (final c in mastered.reversed) ContentText('• $c'),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );

/// Known concepts: a glyph and the count of [mastered].
Widget knownCount(List<String> mastered) => SpokenLabel(
  semanticLabel: 'Known',
  child: GlyphStat(Icons.checklist, '${mastered.length}'),
);
