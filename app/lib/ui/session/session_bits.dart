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

/// A session with nothing to show yet: the first tutor turn (or the
/// request that finds the session) is on its way.
class Preparing extends StatelessWidget {
  /// Creates the wait.
  const new({super.key});

  @override
  Widget build(BuildContext context) => Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const CircularProgressIndicator(),
        const SizedBox(height: AppSpacing.md),
        Text(
          'The tutor is preparing this card...',
          style: Theme.of(context).textTheme.bodyLarge,
        ),
      ],
    ),
  );
}

/// The chat area while there is nothing to show: [waiting] = something is on
/// its way, else the empty state once [loaded], else a spinner.
class NoChat extends StatelessWidget {
  /// Creates the placeholder.
  const new({required this.waiting, required this.loaded, super.key});

  /// A request or a first tutor turn is on its way.
  final bool waiting;

  /// The feed has answered.
  final bool loaded;

  @override
  Widget build(BuildContext context) => waiting
      ? const Preparing()
      : loaded
      ? const EmptyState(
          icon: Icons.chat_bubble_outline,
          title: 'No session yet',
          message:
              'Start one: the tutor first asks what you already know, '
              'then teaches what is missing.',
        )
      : const Center(child: CircularProgressIndicator());
}
