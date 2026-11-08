/// A drill's Run (or Check) and Hint buttons.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';

/// Run/Check, then Hint.
class DrillButtons extends StatelessWidget {
  /// Creates the row.
  const new({
    required this.run,
    required this.hint,
    required this.predict,
    required this.canRun,
    required this.onRun,
    required this.onHint,
    super.key,
  });

  /// Runs the answer.
  final RequestRunner run;

  /// Asks for a hint.
  final RequestRunner hint;

  /// A prediction drill: Check instead of Run.
  final bool predict;

  /// There is an answer to run.
  final bool canRun;

  /// Run pressed.
  final VoidCallback onRun;

  /// Hint pressed.
  final VoidCallback onHint;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      RunnerBuilder(
        run,
        (_) => FilledButton(
          key: ValueKey(predict ? 'check' : 'run'),
          onPressed: run.canSend && canRun ? onRun : null,
          child: Icon(
            predict ? Icons.check : Icons.play_arrow,
            semanticLabel: predict ? 'Check' : 'Run',
          ),
        ),
      ),
      const SizedBox(width: AppSpacing.sm),
      RunnerBuilder(
        hint,
        (_) => OutlinedButton(
          key: const ValueKey('hint'),
          onPressed: hint.canSend ? onHint : null,
          child: const Icon(Icons.lightbulb_outline, semanticLabel: 'Hint'),
        ),
      ),
    ],
  );
}
