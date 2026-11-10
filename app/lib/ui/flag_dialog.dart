/// Asks why a card is flagged. Null when cancelled.
library;

import 'package:flutter/material.dart';
import 'package:tutor/widgets/icon_field.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// Shows the dialog; returns the reason (may be empty) or null. The
/// controller is left to the GC: disposing it when the future completes
/// would race the dialog's exit animation, which still builds the field.
Future<String?> askFlagReason(BuildContext context) {
  final reason = TextEditingController();
  return showDialog<String>(
    context: context,
    builder: (context) => AlertDialog(
      content: FieldLabel(
        semanticLabel: 'What is wrong? (e.g. "the answer is wrong")',
        child: TextField(
          controller: reason,
          autofocus: true,
          maxLines: 3,
          decoration: iconDecoration(Icons.flag_outlined),
          onSubmitted: (v) => Navigator.pop(context, v.trim()),
        ),
      ),
      actions: [
        GlyphButton(
          icon: Icons.close,
          semanticLabel: 'Cancel',
          onPressed: () => Navigator.pop(context),
        ),
        GlyphButton(
          icon: Icons.check,
          semanticLabel: 'Flag',
          filled: true,
          onPressed: () => Navigator.pop(context, reason.text.trim()),
        ),
      ],
    ),
  );
}
