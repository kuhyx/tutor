/// Small parts of the answer composer: the question label and tap-to-fill
/// chips above an answer box, and the answer box itself. The phone's own
/// parts (dots, glyph row) live in `composer_phone.dart`.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/ui/session/composer_phone.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/icon_field.dart';
import 'package:tutor/widgets/spoken_label.dart';

export 'package:tutor/ui/session/composer_drafts.dart';
export 'package:tutor/ui/session/composer_phone.dart';

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
    this.hint = true,
    this.selected,
    super.key,
  });

  /// The choice now in the box (drawn picked); null = none.
  final String? selected;

  /// The "Hint" glyph sits among the chips (the phone has it in its row).
  final bool hint;

  /// The question's choices (may be empty: only "Hint" shows).
  final List<String> choices;

  /// False while a turn is in flight.
  final bool enabled;

  /// A choice was tapped.
  final ValueChanged<String> onPick;

  /// "Hint" was tapped.
  final VoidCallback onHint;

  @override
  Widget build(BuildContext context) => choices.isEmpty && !hint
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
              if (hint)
                GlyphButton(
                  icon: Icons.lightbulb_outline,
                  semanticLabel: 'Hint',
                  onPressed: enabled ? onHint : null,
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
        filled: true,
        onPressed: canSend ? onSend : null,
      ),
    ],
  );
}

/// One answer box: always typeable, even while a turn is in flight.
class AnswerBox extends StatelessWidget {
  /// Creates the box.
  const new({
    required this.controller,
    required this.label,
    required this.minLines,
    required this.maxLines,
    this.dense = false,
    this.focusNode,
    super.key,
  });

  /// Focus owner (the composer opens a closed field and focuses it).
  final FocusNode? focusNode;

  /// The phone session: no pencil, [kPhoneText] text, no bottom gap (it
  /// sits in a row).
  final bool dense;

  /// Its text.
  final TextEditingController controller;

  /// The field's spoken label (nothing is painted).
  final String label;

  /// Lines shown when empty.
  final int minLines;

  /// Lines before it scrolls.
  final int maxLines;

  @override
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.only(bottom: dense ? 0 : AppSpacing.sm),
    child: FieldLabel(
      semanticLabel: label,
      child: TextField(
        controller: controller,
        focusNode: focusNode,
        minLines: minLines,
        maxLines: maxLines,
        style: dense ? const TextStyle(fontSize: kPhoneText) : null,
        decoration: dense
            ? const InputDecoration(isDense: true, border: OutlineInputBorder())
            : iconDecoration(Icons.edit_outlined),
      ),
    ),
  );
}
