/// "I want to learn..." -> `subject_new` (the PC drafts a plan).
library;

import 'package:flutter/material.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';

/// The field and button that send `subject_new`.
class NewSubjectField extends StatefulWidget {
  /// Creates the field.
  const new({required this.runner, required this.onSubmit, super.key});

  /// Shows the request's status.
  final RequestRunner runner;

  /// Sends the text.
  final ValueChanged<String> onSubmit;

  @override
  State<NewSubjectField> createState() => _NewSubjectState();
}

class _NewSubjectState extends State<NewSubjectField> {
  final _text = TextEditingController();

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  void _submit() {
    final text = _text.text.trim();
    if (text.isEmpty || widget.runner.busy) return;
    widget.onSubmit(text);
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      TextField(
        controller: _text,
        maxLength: 2000,
        minLines: 1,
        maxLines: 4,
        textInputAction: TextInputAction.send,
        onSubmitted: (_) => _submit(),
        decoration: const InputDecoration(
          labelText: 'I want to learn...',
          hintText: 'e.g. how a car works',
          border: OutlineInputBorder(),
        ),
      ),
      RequestStatusLine(
        widget.runner,
        queuedText: 'Sent; the PC drafts a plan when it is on...',
      ),
      Align(
        alignment: Alignment.centerRight,
        child: FilledButton(
          onPressed: _submit,
          child: const Text('Draft a plan'),
        ),
      ),
    ],
  );
}
