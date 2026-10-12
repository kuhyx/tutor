/// Asks why a card is flagged. Null when cancelled.
library;

import 'package:flutter/material.dart';

/// Shows the dialog; returns the reason (may be empty) or null. The
/// controller is left to the GC: disposing it when the future completes
/// would race the dialog's exit animation, which still builds the field.
Future<String?> askFlagReason(BuildContext context) {
  final reason = TextEditingController();
  return showDialog<String>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('Flag this card'),
      content: TextField(
        controller: reason,
        autofocus: true,
        maxLines: 3,
        decoration: const InputDecoration(
          labelText: 'What is wrong? (e.g. "the answer is wrong")',
        ),
        onSubmitted: (v) => Navigator.pop(context, v.trim()),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, reason.text.trim()),
          child: const Text('Flag'),
        ),
      ],
    ),
  );
}
