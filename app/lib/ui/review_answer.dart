/// Review's card face (front; once revealed the back, its mnemonic, the
/// excerpt and the source) and answer controls: Show answer, the four
/// ratings (Back's undone rating highlighted), Back and Flag, and their keys.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:tutor/editor/card_rules.dart';
import 'package:tutor/model/card.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/review/review_session.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// The rating's glyph: shape and tint both differ per rating.
IconData gradeIcon(Grade g) => switch (g) {
  Grade.again => Icons.replay,
  Grade.hard => Icons.trending_down,
  Grade.good => Icons.check,
  Grade.easy => Icons.bolt,
};

/// The rating's tint.
Color gradeTint(BuildContext context, Grade g) => switch (g) {
  Grade.again => Theme.of(context).colorScheme.error,
  Grade.hard => AppPalette.warning,
  Grade.good => AppPalette.success,
  Grade.easy => AppPalette.accent,
};

/// The rating's word (spoken only).
String gradeLabel(Grade g) => switch (g) {
  Grade.again => 'Again',
  Grade.hard => 'Hard',
  Grade.good => 'Good',
  Grade.easy => 'Easy',
};

/// The digit key for rating [g].
LogicalKeyboardKey gradeKey(Grade g) => switch (g.value) {
  1 => LogicalKeyboardKey.digit1,
  2 => LogicalKeyboardKey.digit2,
  3 => LogicalKeyboardKey.digit3,
  _ => LogicalKeyboardKey.digit4,
};

/// Back's keys on desktop: Backspace or Ctrl+Z.
const backKeys = [
  SingleActivator(LogicalKeyboardKey.backspace),
  SingleActivator(LogicalKeyboardKey.keyZ, control: true),
];

/// The card: front; once [revealed], back, mnemonic, excerpt and source.
class CardFace extends StatelessWidget {
  /// Creates the face.
  const new(this.card, {required this.revealed, super.key});

  /// The card.
  final StudyCard card;

  /// The answer side shows.
  final bool revealed;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ContentText(card.front, style: text.titleLarge),
            if (revealed) ...[
              const Divider(height: AppSpacing.xl),
              ContentText(card.back, style: text.bodyLarge),
              if (card.mnemonic case final m? when m.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.sm),
                ContentText(m, style: text.bodyMedium),
              ],
              const SizedBox(height: AppSpacing.md),
              ContentText(
                '"${card.excerpt}"',
                style: text.bodyMedium?.copyWith(fontStyle: FontStyle.italic),
              ),
              const SizedBox(height: AppSpacing.xs),
              LinkText(hostOf(card.source), card.source),
            ],
          ],
        ),
      ),
    );
  }
}

/// Show answer, then the ratings; below, Back and Flag (none without
/// [onFlag]: the focus check-in card).
class AnswerBar extends StatelessWidget {
  /// Creates the bar.
  const new(this.run, {required this.onFlag, super.key});

  /// The run.
  final ReviewSession run;

  /// Flag (asks for the reason); null hides Back and Flag.
  final VoidCallback? onFlag;

  @override
  Widget build(BuildContext context) {
    // Back re-shows a card: its earlier rating is the filled one.
    final earlier = run.undoneGrade;
    final lead = earlier ?? Grade.good;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (!run.revealed)
          SpokenLabel(
            semanticLabel: 'Show answer (Space)',
            button: true,
            onTap: run.reveal,
            child: FilledButton(
              onPressed: run.reveal,
              child: const Icon(Icons.visibility_outlined),
            ),
          )
        else ...[
          if (earlier != null)
            SpokenLabel(
              semanticLabel: 'Earlier: ${gradeLabel(earlier)}',
              child: Icon(
                gradeIcon(earlier),
                size: AppTextSize.label,
                color: gradeTint(context, earlier),
              ),
            ),
          if (earlier != null) const SizedBox(height: AppSpacing.xs),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            alignment: WrapAlignment.center,
            children: [
              for (final g in Grade.values)
                GradeButton(
                  grade: g,
                  filled: g == lead,
                  onPressed: () => run.rate(g),
                ),
            ],
          ),
        ],
        if (onFlag case final flag?) ...[
          const SizedBox(height: AppSpacing.sm),
          Wrap(
            alignment: WrapAlignment.center,
            spacing: AppSpacing.sm,
            children: [
              ReviewBack(run),
              GlyphButton(
                icon: Icons.flag_outlined,
                semanticLabel: 'Flag (F)',
                onPressed: flag,
              ),
            ],
          ),
        ],
      ],
    );
  }
}

/// One rating: its digit key and glyph, tinted; [filled] = the lead one.
class GradeButton extends StatelessWidget {
  /// Creates the button.
  const new({
    required this.grade,
    required this.filled,
    required this.onPressed,
    super.key,
  });

  /// The rating.
  final Grade grade;

  /// The lead rating (filled instead of outlined).
  final bool filled;

  /// Rates the card.
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final tint = gradeTint(context, grade);
    final face = Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text('${grade.value}'),
        const SizedBox(width: AppSpacing.xs),
        Icon(gradeIcon(grade)),
      ],
    );
    return SpokenLabel(
      semanticLabel: '${grade.value} ${gradeLabel(grade)}',
      button: true,
      enabled: onPressed != null,
      onTap: onPressed,
      child: filled
          ? FilledButton(
              onPressed: onPressed,
              style: FilledButton.styleFrom(
                backgroundColor: tint,
                foregroundColor: AppPalette.onFill,
              ),
              child: face,
            )
          : OutlinedButton(
              onPressed: onPressed,
              style: OutlinedButton.styleFrom(
                foregroundColor: tint,
                side: BorderSide(color: tint),
              ),
              child: face,
            ),
    );
  }
}

/// Back to the previously rated card (hidden while there is none).
class ReviewBack extends StatelessWidget {
  /// Creates the button.
  const new(this.run, {super.key});

  /// The run.
  final ReviewSession run;

  @override
  Widget build(BuildContext context) => !run.canBack
      ? const SizedBox.shrink()
      : GlyphButton(
          icon: Icons.undo,
          semanticLabel: 'Back',
          onPressed: run.back,
        );
}
