/// The phone's parts of the answer composer: density constants, step dots,
/// and the one row of glyphs around the answer box.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// Phone session density (kuhy, 2026-11-10): question and field text (sp).
const double kPhoneText = 13;

/// Phone session density: glyph size (dp).
const double kPhoneIcon = 20;

/// Phone session density: tap target (dp).
const double kPhoneTarget = 40;

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

/// What "I don't know" sends: the tutor explains the idea and asks an
/// easier question (prompt rule 12).
const kDontKnow = "I don't know";

/// Phone: the lead glyphs ([hint], [dontKnow], and [type] while the field is
/// closed), the answer [field] and the [action] glyph in one row. The tree
/// is the same with the keyboard up or down, so a focused field survives it
/// rising.
class PhoneRow extends StatelessWidget {
  /// Creates the row.
  const new({
    required this.action,
    this.field,
    this.hint,
    this.dontKnow,
    this.type,
    super.key,
  });

  /// The lightbulb (null: a plain box has none).
  final Widget? hint;

  /// "I don't know" (null: a plain box has none).
  final Widget? dontKnow;

  /// Opens the field (only while [field] is null).
  final Widget? type;

  /// The answer box; null = closed (a question with choices).
  final Widget? field;

  /// Next (checkmark) or Send.
  final Widget action;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      ?hint,
      ?dontKnow,
      if (field == null) ?type,
      if (field case final f?) Expanded(child: f) else const Spacer(),
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
