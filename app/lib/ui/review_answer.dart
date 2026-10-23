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

/// The rating's word.
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
            Text(card.front, style: text.titleLarge),
            if (revealed) ...[
              const Divider(height: AppSpacing.xl),
              Text(card.back, style: text.bodyLarge),
              if (card.mnemonic case final m? when m.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(m, style: text.bodyMedium),
              ],
              const SizedBox(height: AppSpacing.md),
              Text(
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

/// Show answer, then the ratings; below, Back and Flag.
class AnswerBar extends StatelessWidget {
  /// Creates the bar.
  const new(this.run, {required this.onFlag, super.key});

  /// The run.
  final ReviewSession run;

  /// Flag (asks for the reason).
  final VoidCallback onFlag;

  @override
  Widget build(BuildContext context) {
    // Back re-shows a card: its earlier rating is the filled one.
    final earlier = run.undoneGrade;
    final lead = earlier ?? Grade.good;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (!run.revealed)
          FilledButton(
            onPressed: run.reveal,
            child: const Text('Show answer (Space)'),
          )
        else ...[
          if (earlier != null)
            Text(
              'Earlier: ${gradeLabel(earlier)}',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          if (earlier != null) const SizedBox(height: AppSpacing.xs),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            alignment: WrapAlignment.center,
            children: [
              for (final g in Grade.values)
                (g == lead ? FilledButton.new : OutlinedButton.new)(
                  onPressed: () => run.rate(g),
                  child: Text('${g.value} ${gradeLabel(g)}'),
                ),
            ],
          ),
        ],
        const SizedBox(height: AppSpacing.sm),
        Wrap(
          alignment: WrapAlignment.center,
          spacing: AppSpacing.sm,
          children: [
            ReviewBack(run),
            TextButton.icon(
              onPressed: onFlag,
              icon: const Icon(Icons.flag_outlined),
              label: const Text('Flag (F)'),
            ),
          ],
        ),
      ],
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
      : TextButton.icon(
          onPressed: run.back,
          icon: const Icon(Icons.undo),
          label: const Text('Back'),
        );
}
