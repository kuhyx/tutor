/// History's "Ask a follow-up" (kuhy, 2026-10-20): for a session whose card
/// was done in it, reopen it (`follow_up_open`), send the question as a
/// `message`, then open the session. The PC refuses (`session_live`) while
/// another session is live; the question then stays in the box.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/util/device.dart';

/// The box and its Ask button.
class FollowUpBox extends StatefulWidget {
  /// Creates the box for session [sid].
  const new({
    required this.sid,
    required this.runner,
    required this.onAsked,
    super.key,
  });

  /// The finished session.
  final String sid;

  /// Runs the requests (its status line shows progress and refusals).
  final RequestRunner runner;

  /// Called once the question is sent: opens the session.
  final Future<void> Function() onAsked;

  @override
  State<FollowUpBox> createState() => _FollowUpBoxState();
}

class _FollowUpBoxState extends State<FollowUpBox> {
  final _text = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _ask() async {
    final text = _text.text.trim();
    if (text.isEmpty || _busy) return;
    setState(() => _busy = true);
    try {
      final opened = await widget.runner.run(
        RequestBody.followUpOpen(widget.sid),
      );
      if (opened is! RelayDone) return;
      final sent = await widget.runner.run(
        RequestBody.message(widget.sid, text).withDevice(deviceName),
      );
      if (sent is RelayDone) await widget.onAsked();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.end,
    children: [
      Expanded(
        child: TextField(
          controller: _text,
          minLines: 1,
          maxLines: 4,
          decoration: const InputDecoration(labelText: 'Ask a follow-up'),
        ),
      ),
      const SizedBox(width: AppSpacing.sm),
      FilledButton(onPressed: _busy ? null : _ask, child: const Text('Ask')),
    ],
  );
}
