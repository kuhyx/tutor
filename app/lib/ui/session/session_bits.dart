/// Small parts of the Session's bottom panel.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/ui/common.dart';

/// Card done: Next card / Stop here.
class CardEnd extends StatelessWidget {
  /// Creates the bar.
  const new({required this.onNext, required this.onStop, super.key});

  /// Next card (stops this session, starts the next).
  final VoidCallback onNext;

  /// Stop here.
  final VoidCallback onStop;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      const Expanded(child: Text('Card done ✓')),
      OutlinedButton(onPressed: onStop, child: const Text('Stop here')),
      const SizedBox(width: AppSpacing.sm),
      FilledButton(
        autofocus: true,
        onPressed: onNext,
        child: const Text('Next card'),
      ),
    ],
  );
}

/// The request status, plus Continue when the session is no longer live.
class NotLiveStatus extends StatelessWidget {
  /// Creates the line.
  const new({
    required this.runner,
    required this.view,
    required this.onRun,
    super.key,
  });

  /// Runner.
  final RequestRunner runner;

  /// Session on screen.
  final SessionView? view;

  /// Runs `session_resume`.
  final Future<RelayStatus> Function(RequestBody body) onRun;

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<RelayStatus?>(
    valueListenable: runner.status,
    builder: (context, s, _) => Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        RequestStatusLine(runner),
        if (s is RelayFailed && s.code == 'not_live' && view != null)
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton(
              onPressed: () => onRun(RequestBody.sessionResume(view!.sid)),
              child: const Text('Continue this session'),
            ),
          ),
      ],
    ),
  );
}
