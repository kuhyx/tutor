/// "I want to learn..." -> `subject_new` (the PC drafts a plan).
library;

import 'package:flutter/material.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';

/// The field and button that send `subject_new`. Both lock while the
/// request is in flight; success clears the text, failure keeps it.
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

  // Set from a press until its request ends, so the runner's other requests
  // (Finish subject) never clear the box.
  bool _sent = false;

  @override
  void initState() {
    super.initState();
    widget.runner.status.addListener(_onStatus);
  }

  @override
  void dispose() {
    widget.runner.status.removeListener(_onStatus);
    _text.dispose();
    super.dispose();
  }

  void _onStatus() {
    if (!_sent || widget.runner.busy) return;
    _sent = false;
    if (widget.runner.status.value is RelayDone) _text.clear();
  }

  void _submit() {
    final text = _text.text.trim();
    if (text.isEmpty || !widget.runner.canSend) return;
    _sent = true;
    widget.onSubmit(text);
  }

  @override
  Widget build(BuildContext context) =>
      RunnerBuilder(widget.runner, (_) => _column());

  Widget _column() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      TextField(
        controller: _text,
        enabled: !widget.runner.busy,
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
          onPressed: widget.runner.canSend ? _submit : null,
          child: const Text('Draft a plan'),
        ),
      ),
    ],
  );
}
