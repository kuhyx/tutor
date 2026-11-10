/// Small parts of the answer composer: the question label and tap-to-fill
/// chips above an answer box, and the phone's step dots and its one row
/// hint, field, action.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/icon_field.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// Phone session density (kuhy, 2026-11-10): question and field text (sp).
const double kPhoneText = 13;

/// Phone session density: glyph size (dp).
const double kPhoneIcon = 20;

/// Phone session density: tap target (dp).
const double kPhoneTarget = 40;

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
    super.key,
  });

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

/// Phone: one dot per question, the current one filled (no "1/3" text;
/// the position is spoken only).
class StepDots extends StatelessWidget {
  /// Creates the dots for step [step] (0-based) of [total].
  const new({required this.step, required this.total, super.key});

  /// Current step, 0-based.
  final int step;

  /// Number of questions.
  final int total;

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    return SpokenLabel(
      key: const ValueKey('step-dots'),
      semanticLabel: '${step + 1}/$total',
      child: Padding(
        padding: const EdgeInsets.only(bottom: AppSpacing.xs),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            for (var i = 0; i < total; i++)
              Container(
                width: 8,
                height: 8,
                margin: const EdgeInsets.symmetric(horizontal: 3),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: i == step ? color.primary : color.outlineVariant,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Phone: [hint] (optional), the answer [field] and the [action] glyph in
/// one row.
class PhoneRow extends StatelessWidget {
  /// Creates the row.
  const new({required this.field, required this.action, this.hint, super.key});

  /// The lightbulb (null: a plain box has none).
  final Widget? hint;

  /// The answer box.
  final Widget field;

  /// Next (checkmark) or Send.
  final Widget action;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      ?hint,
      Expanded(child: field),
      const SizedBox(width: AppSpacing.xs),
      action,
    ],
  );
}

/// A dense phone glyph button ([kPhoneIcon] glyph, [kPhoneTarget] target).
GlyphButton phoneGlyph(
  IconData icon,
  String semanticLabel,
  VoidCallback? onPressed, {
  bool filled = false,
}) => GlyphButton(
  icon: icon,
  semanticLabel: semanticLabel,
  onPressed: onPressed,
  filled: filled,
  size: kPhoneIcon,
  target: kPhoneTarget,
);

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
    this.dense = false,
    super.key,
  });

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
