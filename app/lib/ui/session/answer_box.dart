/// One answer box of the composer: the pencil and, for a question, the
/// "Hint" bulb right beside it inside the box (kuhy, 2026-11-22).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/ui/session/composer_phone.dart';
import 'package:tutor/widgets/icon_field.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// The in-box hint bulb: glyph size (muted, rarely used).
const double kHintGlyph = 16;

/// The in-box hint bulb: tap target.
const double kHintTarget = 28;

// The pencil's inset from the box's left edge, and its size.
const double _pencilInset = 12;
const double _pencil = 24;

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
    this.hint = false,
    this.onHint,
    super.key,
  });

  /// Focus owner (the composer opens a closed field and focuses it).
  final FocusNode? focusNode;

  /// The phone session: no pencil, [kPhoneText] text, no bottom gap (it
  /// sits in a row).
  final bool dense;

  /// A "Hint" bulb sits inside the box, right beside the pencil.
  final bool hint;

  /// The bulb's tap (sends "Hint"); null = inert (a turn in flight).
  final VoidCallback? onHint;

  /// Its text.
  final TextEditingController controller;

  /// The field's spoken label (nothing is painted).
  final String label;

  /// Lines shown when empty.
  final int minLines;

  /// Lines before it scrolls.
  final int maxLines;

  // The leading slot: the pencil (not on the phone), then room for the bulb.
  Widget? _prefix() {
    if (!hint) return dense ? null : const Icon(Icons.edit_outlined);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (!dense) ...[
          const SizedBox(width: _pencilInset),
          const Icon(Icons.edit_outlined),
        ] else
          const SizedBox(width: AppSpacing.xs),
        const SizedBox(width: kHintTarget + AppSpacing.xs),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final field = FieldLabel(
      semanticLabel: label,
      child: TextField(
        controller: controller,
        focusNode: focusNode,
        minLines: minLines,
        maxLines: maxLines,
        style: dense ? const TextStyle(fontSize: kPhoneText) : null,
        decoration: InputDecoration(
          prefixIcon: _prefix(),
          // Phone: the bulb's slot must not lift the one-line field to
          // Material's 48 dp icon minimum (it stays 44 dp, as without it).
          prefixIconConstraints: dense
              ? const BoxConstraints(minWidth: kHintTarget)
              : null,
          isDense: dense,
          border: const OutlineInputBorder(),
        ),
      ),
    );
    return Padding(
      padding: EdgeInsets.only(bottom: dense ? 0 : AppSpacing.sm),
      // The bulb is the field's sibling, not inside its MergeSemantics: it
      // stays its own "Hint" button for screen readers and finders.
      child: hint
          ? Stack(
              children: [
                field,
                Positioned(
                  left: dense
                      ? AppSpacing.xs
                      : _pencilInset + _pencil + AppSpacing.xs / 2,
                  top: 0,
                  bottom: 0,
                  width: kHintTarget,
                  child: Center(
                    child: GlyphButton(
                      icon: Icons.lightbulb_outline,
                      semanticLabel: 'Hint',
                      tooltip: (l) => l.tooltip_hint,
                      size: kHintGlyph,
                      target: kHintTarget,
                      tint: Theme.of(context).colorScheme.onSurfaceVariant,
                      onPressed: onHint,
                    ),
                  ),
                ),
              ],
            )
          : field,
    );
  }
}
