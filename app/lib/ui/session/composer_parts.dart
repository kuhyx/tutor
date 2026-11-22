/// Small parts of the answer composer: the question label and tap-to-fill
/// chips above an answer box, and the Send row (the box itself is in
/// `answer_box.dart`). The phone's own
/// parts (dots, glyph row) live in `composer_phone.dart`.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/spoken_label.dart';

export 'package:tutor/ui/session/answer_box.dart';
export 'package:tutor/ui/session/composer_drafts.dart';
export 'package:tutor/ui/session/composer_phone.dart';

/// The tutor's suggested answers as chips (the "Hint" bulb is inside the
/// answer box, `AnswerBox.hint`).
class AnswerChips extends StatelessWidget {
  /// Creates the chips; [onPick] gets the tapped choice (it only fills the
  /// box, so it always works).
  const new({
    required this.choices,
    required this.onPick,
    this.selected,
    super.key,
  });

  /// The choice now in the box (drawn picked); null = none.
  final String? selected;

  /// The question's choices (empty: no row at all).
  final List<String> choices;

  /// A choice was tapped.
  final ValueChanged<String> onPick;

  @override
  Widget build(BuildContext context) => choices.isEmpty
      ? const SizedBox.shrink()
      : Padding(
          padding: const EdgeInsets.only(bottom: AppSpacing.sm),
          child: Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.xs,
            children: [
              for (final c in choices)
                ActionChip(
                  visualDensity: VisualDensity.compact,
                  backgroundColor: c == selected
                      ? Theme.of(context).colorScheme.primaryContainer
                      : null,
                  label: ContentText(c),
                  onPressed: () => onPick(c),
                ),
            ],
          ),
        );
}

/// A question above its answer box, selectable so it can be copied.
class QuestionLabel extends StatelessWidget {
  /// Creates the label for [asked]; [fontSize] null = the theme's.
  const new(this.asked, {this.fontSize, super.key});

  /// The question.
  final Asked asked;

  /// Text size (the phone's density); null = labelLarge's.
  final double? fontSize;

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.labelLarge
        ?.copyWith(fontSize: fontSize);
    return SelectionArea(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SpokenLabel(
            semanticLabel: asked.heading,
            child: Text(asked.label, style: style),
          ),
          if (asked.check)
            const Padding(
              padding: EdgeInsets.only(left: AppSpacing.xs),
              child: Icon(Icons.fact_check_outlined, size: AppTextSize.label),
            ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(child: ContentText(asked.text, style: style)),
        ],
      ),
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
            : Align(
                alignment: Alignment.centerLeft,
                child: SpokenLabel(
                  semanticLabel: hint!,
                  child: const Icon(Icons.keyboard_outlined),
                ),
              ),
      ),
      GlyphButton(
        icon: Icons.send,
        semanticLabel: 'Send',
        tooltip: (l) => l.tooltip_send,
        filled: true,
        onPressed: canSend ? onSend : null,
      ),
    ],
  );
}
