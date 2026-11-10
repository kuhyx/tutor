/// Glyph vocabulary of the learning screens (Review, Drill, Editor, Plan,
/// Progress): empty states, tallies, module marks, status snacks and tiles.
/// Words are never painted; the old wording is the spoken label.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/progress/terms.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// A big outline glyph (and optional numbers) for an empty or finished list;
/// [semanticLabel] is what it used to say.
class GlyphEmpty extends StatelessWidget {
  /// Creates the placeholder.
  const new({
    required this.icon,
    required this.semanticLabel,
    this.stats = const [],
    this.tint,
    super.key,
  });

  /// Glyph colour; null = muted.
  final Color? tint;

  /// The glyph.
  final IconData icon;

  /// The old headline and sentence, spoken only.
  final String semanticLabel;

  /// Numbers under the glyph.
  final List<Widget> stats;

  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.xl),
      child: SpokenLabel(
        semanticLabel: semanticLabel,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 64,
              color: tint ?? Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            if (stats.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.md),
              Wrap(spacing: AppSpacing.md, children: stats),
            ],
          ],
        ),
      ),
    ),
  );
}

/// A transient icon-only snack: [kind] glyph on a tinted chip.
void showCueSnack(BuildContext context, CueKind kind, String semanticLabel) {
  ScaffoldMessenger.maybeOf(context)
    ?..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        duration: kind == CueKind.error
            ? const Duration(seconds: 5)
            : const Duration(seconds: 3),
        content: Align(
          alignment: Alignment.centerLeft,
          child: CueChip(kind: kind, semanticLabel: semanticLabel),
        ),
      ),
    );
}

/// Done / recalled / due as glyph + number marks; `total` shows `x/y` done.
class TallyRow extends StatelessWidget {
  /// Creates the row.
  const new(this.tally, {this.total = false, this.size, super.key});

  /// The counts.
  final Tally tally;

  /// `x/y` for done (the whole subject), else just `x`.
  final bool total;

  /// Number size.
  final double? size;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final label = total ? tally.summary : tally.doneText;
    return SpokenLabel(
      semanticLabel: '$label. $tallyHelp',
      child: Wrap(
        spacing: AppSpacing.md,
        runSpacing: AppSpacing.xs,
        children: [
          GlyphStat(
            Icons.check_circle,
            total ? '${tally.taught}/${tally.cards}' : '${tally.taught}',
            color: scheme.primary,
            size: size,
          ),
          GlyphStat(
            Icons.star,
            '${tally.mastered}',
            color: AppPalette.warning,
            size: size,
          ),
          if (tally.due > 0)
            GlyphStat(
              Icons.schedule,
              '${tally.due}',
              color: scheme.error,
              size: size,
            ),
        ],
      ),
    );
  }
}

/// The glyph of a [ModuleMark].
IconData moduleMarkIcon(ModuleMark m) => switch (m) {
  ModuleMark.locked => Icons.lock_outline,
  ModuleMark.generating => Icons.autorenew,
  ModuleMark.ready => Icons.play_circle_outline,
  ModuleMark.failed => Icons.error_outline,
  ModuleMark.done => Icons.check_circle_outline,
  ModuleMark.reviewed => Icons.verified,
};

/// The tint of a [ModuleMark] (shape and tint both differ).
Color moduleMarkColor(BuildContext context, ModuleMark m) {
  final scheme = Theme.of(context).colorScheme;
  return switch (m) {
    ModuleMark.locked => scheme.outline,
    ModuleMark.generating => AppPalette.warning,
    ModuleMark.ready => scheme.primary,
    ModuleMark.failed => scheme.error,
    ModuleMark.done => scheme.primary,
    ModuleMark.reviewed => AppPalette.success,
  };
}

/// A module's mark; its old word (and explanation) is the spoken label.
class ModuleMarkIcon extends StatelessWidget {
  /// Creates the mark.
  const new(this.mark, {this.size, super.key});

  /// Which mark.
  final ModuleMark mark;

  /// Glyph size.
  final double? size;

  @override
  Widget build(BuildContext context) => SpokenLabel(
    semanticLabel: [mark.name, ?badgeHelp(mark.name)].join('. '),
    child: Icon(
      moduleMarkIcon(mark),
      size: size,
      color: moduleMarkColor(context, mark),
    ),
  );
}

/// Recall as a percent number (`62%`), tinted like a bar.
class RecallStat extends StatelessWidget {
  /// Creates the stat.
  const new(this.recall, {this.size, super.key});

  /// 0..1.
  final double recall;

  /// Number size.
  final double? size;

  @override
  Widget build(BuildContext context) => SpokenLabel(
    semanticLabel: 'recall ${(recall * 100).round()}%',
    child: GlyphStat(
      Icons.psychology_outlined,
      '${(recall * 100).round()}%',
      size: size,
    ),
  );
}
