/// The phone composer's one-question view: step dots, the question (swipe
/// right = the previous one) and one row [hint][don't know][field][check /
/// send]. The tree is the same with the keyboard up or down, so a focused
/// field survives the keyboard rising; typing only drops the chips and caps
/// the question at [kTypingShare] of the room above the keyboard.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/ui/fit_pages.dart';
import 'package:tutor/ui/session/composer_parts.dart';

/// Typing: the question takes at most this share of the visible height.
const double kTypingShare = 0.4;

/// The step on screen.
class PhoneStep extends StatefulWidget {
  /// Creates the view of question [step] of [asked].
  const new({
    required this.asked,
    required this.step,
    required this.typing,
    required this.fieldOpen,
    required this.enabled,
    required this.canSend,
    required this.chips,
    required this.field,
    required this.onGo,
    required this.onHint,
    required this.onDontKnow,
    required this.onOpenField,
    required this.onSend,
    super.key,
  });

  /// The questions.
  final List<Asked> asked;

  /// The question on screen.
  final int step;

  /// The keyboard is up over the boxes.
  final bool typing;

  /// The field shows (else the keyboard glyph does).
  final bool fieldOpen;

  /// A reply may be sent now.
  final bool enabled;

  /// There is something to send.
  final bool canSend;

  /// The choices chips of question `i`.
  final Widget Function(int i) chips;

  /// The answer box of question `i`.
  final Widget Function(int i) field;

  /// Moves to another question.
  final void Function(int step) onGo;

  /// Asks for a hint.
  final VoidCallback onHint;

  /// Sends "I don't know".
  final VoidCallback onDontKnow;

  /// Opens the closed field.
  final VoidCallback onOpenField;

  /// Sends the answers.
  final VoidCallback onSend;

  @override
  State<PhoneStep> createState() => _PhoneStepState();
}

class _PhoneStepState extends State<PhoneStep> {
  Offset _swipe = Offset.zero; // the drag on the question so far

  // Swipe right on the question: the previous one. Raw pointers, so the
  // question's SelectionArea cannot win the drag in the arena.
  Widget _question() => Listener(
    onPointerDown: (e) => _swipe = Offset.zero,
    onPointerMove: (e) => _swipe += e.delta,
    onPointerUp: (_) {
      final d = _swipe;
      if (d.dx > kPhoneTarget && d.dx > 2 * d.dy.abs() && widget.step > 0) {
        widget.onGo(widget.step - 1);
      }
    },
    // Pages, never a scroll (build-mobile-app R7): a long question pages.
    child: FitPages(
      key: ValueKey('step-${widget.step}'),
      children: [
        QuestionLabel(widget.asked[widget.step], fontSize: kPhoneText),
        const SizedBox(height: AppSpacing.sm),
        widget.chips(widget.step),
      ],
    ),
  );

  Widget _row() {
    final last = widget.step == widget.asked.length - 1;
    final w = widget;
    return PhoneRow(
      hint: phoneGlyph(
        Icons.lightbulb_outline,
        'Hint',
        w.enabled ? w.onHint : null,
      ),
      dontKnow: phoneGlyph(
        Icons.help_outline,
        kDontKnow,
        w.enabled ? w.onDontKnow : null,
      ),
      type: phoneGlyph(Icons.keyboard_outlined, 'Type', w.onOpenField),
      field: w.fieldOpen ? w.field(w.step) : null,
      action: last
          ? phoneGlyph(
              Icons.send,
              'Send',
              w.canSend ? w.onSend : null,
              filled: true,
            )
          : phoneGlyph(
              Icons.check,
              'Next',
              () => w.onGo(w.step + 1),
              filled: true,
            ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final m = MediaQuery.of(context);
    final room = m.size.height - m.viewInsets.bottom - m.padding.vertical;
    final question = _question();
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (widget.asked.length > 1)
          StepDots(step: widget.step, total: widget.asked.length),
        // Typing: the question takes what it needs, up to its share; the
        // message above keeps the rest. Otherwise it shares the room.
        if (widget.typing)
          ConstrainedBox(
            constraints: BoxConstraints(maxHeight: room * kTypingShare),
            child: question,
          )
        else
          Flexible(child: question),
        _row(),
      ],
    );
  }
}
