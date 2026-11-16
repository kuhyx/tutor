/// The composer's frame: Ctrl+Enter sends; on the desktop a box per question
/// with its chips, on the phone one question at a time (or one plain row).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/ui/session/composer_parts.dart';

/// The composer's boxes laid out.
class ComposerLayout extends StatelessWidget {
  /// Creates the layout; the builders make the state-owning parts.
  const new({
    required this.asked,
    required this.phone,
    required this.canSend,
    required this.plainLabel,
    required this.field,
    required this.chips,
    required this.onSend,
    required this.step,
    super.key,
  });

  /// The questions (none: the plain box).
  final List<Asked> asked;

  /// The Android app.
  final bool phone;

  /// There is something to send now.
  final bool canSend;

  /// The plain box's spoken label.
  final String plainLabel;

  /// The answer box `i` with its spoken label.
  final Widget Function(int i, String label) field;

  /// The choices chips of question `i`.
  final Widget Function(int i) chips;

  /// Sends the composed text.
  final VoidCallback onSend;

  /// The phone's one-question view.
  final Widget Function() step;

  @override
  Widget build(BuildContext context) {
    final body = CallbackShortcuts(
      bindings: {
        const SingleActivator(LogicalKeyboardKey.enter, control: true): onSend,
      },
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (asked.isEmpty && phone)
            PhoneRow(
              field: field(0, plainLabel),
              action: phoneGlyph(
                Icons.send,
                'Send',
                canSend ? onSend : null,
                filled: true,
              ),
            )
          else if (asked.isEmpty) ...[
            field(0, plainLabel),
            SendRow(
              canSend: canSend,
              onSend: onSend,
              hint: 'Ctrl+Enter to send',
            ),
          ] else if (phone)
            Flexible(child: step())
          else ...[
            for (final (i, a) in asked.indexed) ...[
              QuestionLabel(a),
              const SizedBox(height: AppSpacing.xs),
              chips(i),
              field(i, 'Your answer'),
            ],
            SendRow(
              canSend: canSend,
              onSend: onSend,
              hint: 'Ctrl+Enter to send',
            ),
          ],
        ],
      ),
    );
    // Phone: the step view takes the panel's height (flex child).
    return phone ? Flexible(child: body) : body;
  }
}
