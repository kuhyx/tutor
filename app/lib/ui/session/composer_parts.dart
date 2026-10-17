/// Small parts of the answer composer: the tap-to-fill chips above an answer
/// box and the phone's step bar (1/3, Back, Next / Send).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// The tutor's suggested answers as chips, plus a fixed "Hint" chip.
class AnswerChips extends StatelessWidget {
  /// Creates the chips; [onPick] gets the tapped choice (it only fills the
  /// box, so it always works), [onHint] sends "Hint" and is inert while
  /// [enabled] is false (a turn in flight).
  const new({
    required this.choices,
    required this.enabled,
    required this.onPick,
    required this.onHint,
    super.key,
  });

  /// The question's choices (may be empty: only "Hint" shows).
  final List<String> choices;

  /// False while a turn is in flight.
  final bool enabled;

  /// A choice was tapped.
  final ValueChanged<String> onPick;

  /// "Hint" was tapped.
  final VoidCallback onHint;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: AppSpacing.sm),
    child: Wrap(
      spacing: AppSpacing.sm,
      runSpacing: AppSpacing.xs,
      children: [
        for (final c in choices)
          ActionChip(
            visualDensity: VisualDensity.compact,
            label: Text(c),
            onPressed: () => onPick(c),
          ),
        ActionChip(
          visualDensity: VisualDensity.compact,
          avatar: const Icon(Icons.lightbulb_outline, size: 18),
          label: const Text('Hint'),
          onPressed: enabled ? onHint : null,
        ),
      ],
    ),
  );
}

/// Phone: "2/3", Back, and Next (Send on the last step).
class StepBar extends StatelessWidget {
  /// Creates the bar for step [step] (0-based) of [total].
  const new({
    required this.step,
    required this.total,
    required this.canSend,
    required this.onBack,
    required this.onNext,
    required this.onSend,
    super.key,
  });

  /// Current step, 0-based.
  final int step;

  /// Number of questions.
  final int total;

  /// Send is allowed (something typed, no turn in flight).
  final bool canSend;

  /// Previous question.
  final VoidCallback onBack;

  /// Next question.
  final VoidCallback onNext;

  /// Send every answer as one message.
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    final last = step == total - 1;
    return Row(
      children: [
        if (total > 1)
          Expanded(
            child: Text(
              '${step + 1}/$total',
              style: Theme.of(context).textTheme.labelLarge,
            ),
          )
        else
          const Spacer(),
        if (step > 0) TextButton(onPressed: onBack, child: const Text('Back')),
        const SizedBox(width: AppSpacing.sm),
        FilledButton(
          onPressed: last ? (canSend ? onSend : null) : onNext,
          child: Text(last ? 'Send' : 'Next'),
        ),
      ],
    );
  }
}

/// Desktop and plain box: the keyboard hint (none on the phone) and Send.
class SendRow extends StatelessWidget {
  /// Creates the row.
  const new({
    required this.canSend,
    required this.onSend,
    this.hint,
    super.key,
  });

  /// Send is allowed.
  final bool canSend;

  /// Sends.
  final VoidCallback onSend;

  /// Shortcut hint; null = none.
  final String? hint;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Expanded(
        child: hint == null
            ? const SizedBox.shrink()
            : Text(hint!, style: Theme.of(context).textTheme.bodySmall),
      ),
      FilledButton(
        onPressed: canSend ? onSend : null,
        child: const Text('Send'),
      ),
    ],
  );
}

/// Fills each box of [boxes] that is still empty from the draft [saved], so
/// a draft read that lands late never overwrites what was typed meanwhile.
/// Extra entries (an old draft's comment box) are ignored.
void fillEmptyBoxes(List<TextEditingController> boxes, List<String> saved) {
  for (final (i, v) in saved.indexed) {
    if (i < boxes.length && boxes[i].text.isEmpty) boxes[i].text = v;
  }
}

/// The step to resume on: the first of [questions] boxes still empty, else
/// the last.
int resumeStep(List<TextEditingController> boxes, int questions) {
  for (var i = 0; i < questions; i++) {
    if (boxes[i].text.isEmpty) return i;
  }
  return questions - 1;
}

/// One answer box: always typeable, even while a turn is in flight.
class AnswerBox extends StatelessWidget {
  /// Creates the box.
  const new({
    required this.controller,
    required this.label,
    required this.minLines,
    required this.maxLines,
    super.key,
  });

  /// Its text.
  final TextEditingController controller;

  /// Floating label.
  final String label;

  /// Lines shown when empty.
  final int minLines;

  /// Lines before it scrolls.
  final int maxLines;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: AppSpacing.sm),
    child: TextField(
      controller: controller,
      minLines: minLines,
      maxLines: maxLines,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
    ),
  );
}
