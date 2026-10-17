/// Review's answer controls: Show answer, the four ratings (Back's undone
/// rating highlighted), Back and Flag, and their keys.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/review/review_session.dart';

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
