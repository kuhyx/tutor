import 'package:flutter/material.dart';
import 'package:tutor/coach/coach_requests.dart';
import 'package:tutor/ui/sql/data_grid.dart';

/// Asks the user to type `reveal`; true only when they did and confirmed.
Future<bool> askReveal(BuildContext context) async =>
    await showDialog<bool>(
      context: context,
      builder: (_) => const _RevealDialog(),
    ) ??
    false;

class _RevealDialog extends StatefulWidget {
  const new();

  @override
  State<_RevealDialog> createState() => _RevealDialogState();
}

class _RevealDialogState extends State<_RevealDialog> {
  final _text = TextEditingController();

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    content: TextField(
      key: const ValueKey('reveal-text'),
      controller: _text,
      autofocus: true,
      autocorrect: false,
      style: sqlMono,
      decoration: const InputDecoration(hintText: coachReveal),
    ),
    actions: [
      IconButton(
        key: const ValueKey('reveal-cancel'),
        onPressed: () => Navigator.of(context).pop(false),
        icon: const Icon(Icons.close, semanticLabel: 'Cancel'),
      ),
      ListenableBuilder(
        listenable: _text,
        builder: (context, _) => IconButton.filled(
          key: const ValueKey('reveal-ok'),
          onPressed: _text.text.trim() == coachReveal
              ? () => Navigator.of(context).pop(true)
              : null,
          icon: const Icon(Icons.visibility, semanticLabel: 'Reveal'),
        ),
      ),
    ],
  );
}
