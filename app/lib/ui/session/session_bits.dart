/// Small parts of the Session's bottom panel.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/session/blocked_panel.dart';

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
      // No autofocus: the follow-up composer below takes the keys.
      FilledButton(onPressed: onNext, child: const Text('Next card')),
    ],
  );
}

/// Start session (or continue the subject's open one).
class StartButton extends StatelessWidget {
  /// Creates the button.
  const new({required this.onStart, super.key});

  /// Starts.
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) => Align(
    alignment: Alignment.centerRight,
    child: FilledButton(onPressed: onStart, child: const Text('Start session')),
  );
}

/// The request status, plus Continue when the session is no longer live;
/// a blocking result (cap, locked, no card left) shows its call to action
/// instead ([BlockedPanel]).
class NotLiveStatus extends StatelessWidget {
  /// Creates the line.
  const new({
    required this.services,
    required this.runner,
    required this.view,
    required this.onRun,
    this.subject,
    super.key,
  });

  /// Services (the catalog and Review, for the call to action).
  final TutorServices services;

  /// The screen's subject (a hint when a block names none).
  final String? subject;

  /// Runner.
  final RequestRunner runner;

  /// Session on screen.
  final SessionView? view;

  /// Runs a request (`session_resume`, or the block's fix).
  final Future<RelayStatus> Function(RequestBody body) onRun;

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<RelayStatus?>(
    valueListenable: runner.status,
    builder: (context, s, _) => Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // A block is a call to action, shown once (not also as a status).
        if (s is RelayFailed && s.blocks)
          BlockedPanel(
            services: services,
            blocked: s.blocked!,
            text: s.text,
            subject: subject,
            lastBody: runner.lastBody,
            onRun: onRun,
          )
        else
          RequestStatusLine(runner, stalledText: noReplyText),
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

/// The bottom panel's frame: on the phone the step bar stays pinned and
/// the composer scrolls itself; elsewhere the whole panel scrolls.
Widget sessionPanel(Widget child, {required bool phone}) => phone
    ? Padding(padding: const EdgeInsets.all(AppSpacing.md), child: child)
    : SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: child,
      );

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
