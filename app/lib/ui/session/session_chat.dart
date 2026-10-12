/// The Session's chat column: status line with paused/stalled pills, the
/// messages, the pending learner bubble and busy phase, then Card done
/// (Next card / Stop here), the composer, or Start.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/session/composer.dart';
import 'package:tutor/ui/session/message_tile.dart';
import 'package:tutor/ui/session/session_bits.dart';

/// The chat column.
class SessionChat extends StatefulWidget {
  /// Creates the column.
  const new({
    required this.services,
    required this.feed,
    required this.view,
    required this.runner,
    required this.scroll,
    required this.now,
    required this.onRun,
    required this.onSend,
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// The feed (for "loaded").
  final SessionFeed feed;

  /// Session on screen.
  final SessionView? view;

  /// Request runner.
  final RequestRunner runner;

  /// Chat scroller.
  final ScrollController scroll;

  /// Clock.
  final DateTime Function() now;

  /// Runs a request.
  final Future<RelayStatus> Function(RequestBody body) onRun;

  /// Sends a learner message.
  final Future<bool> Function(String sid, String text) onSend;

  @override
  State<SessionChat> createState() => _SessionChatState();
}

class _SessionChatState extends State<SessionChat> {
  int _count = -1;

  // New messages scroll to the bottom (as renderLog does).
  void _follow(int count) {
    if (count == _count) return;
    _count = count;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final s = widget.scroll;
      if (s.hasClients) s.jumpTo(s.position.maxScrollExtent);
    });
  }

  @override
  Widget build(BuildContext context) {
    final view = widget.view;
    final meta = view?.meta;
    final text = Theme.of(context).textTheme;
    final live = meta != null && !meta.stopped;
    final busy = meta?.busy;
    final messages = view?.messages ?? const <KeyedMessage>[];
    final last = view?.last;
    final boxes =
        live &&
        !meta.cardDone &&
        last != null &&
        last.message.role == 'tutor' &&
        askedOf(last.message).isNotEmpty;
    _follow(messages.length + (busy == null ? 0 : 1));
    final clock = meta?.clock;
    return Column(
      children: [
        if (meta != null)
          Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.md,
              AppSpacing.sm,
              AppSpacing.md,
              0,
            ),
            child: Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.xs,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Text(
                  'Active ${(clock!.activeSeconds / 60).floor()} min'
                  ' · credited ${meta.creditedMinutes}',
                  style: text.bodySmall,
                ),
                if (clock.pausedReason != null)
                  Pill('Clock paused: ${clock.pausedReason}', warn: true),
                if (live &&
                    clock.stalledAt(widget.now().millisecondsSinceEpoch))
                  const Pill('Stalled: no reply for 10 min', warn: true),
                if (meta.stopped) const Pill('Stopped'),
              ],
            ),
          ),
        PcOfflineBanner(widget.services.presence.state),
        Expanded(
          child: view == null
              ? (widget.feed.loaded.value
                    ? const EmptyState(
                        icon: Icons.chat_bubble_outline,
                        title: 'No session yet',
                        message:
                            'Start one: the tutor first asks what you '
                            'already know, then teaches what is missing.',
                      )
                    : const Center(child: CircularProgressIndicator()))
              : ListView(
                  controller: widget.scroll,
                  padding: const EdgeInsets.all(AppSpacing.md),
                  children: [
                    for (final (i, m) in messages.indexed)
                      MessageTile(
                        message: m.message,
                        questionsAsBoxes: boxes && i == messages.length - 1,
                        onReport: m.message.role == 'tutor'
                            ? () => showReport(
                                context,
                                widget.services,
                                route: '/session',
                                session: view.sid,
                                msg: m.key,
                                preview: m.message.text,
                              )
                            : null,
                      ),
                    if (busy != null && (busy.text ?? '').isNotEmpty)
                      MessageTile(
                        message: Message(role: 'learner', text: busy.text!),
                        pending: true,
                      ),
                    if (busy != null)
                      Text(phaseText(busy.phase), style: text.bodyMedium),
                  ],
                ),
        ),
        const Divider(height: 1),
        // The composer never takes more than ~40% of the height: the chat
        // stays the main scroller, the boxes scroll inside this panel.
        ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.sizeOf(context).height * 0.4,
          ),
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                NotLiveStatus(
                  runner: widget.runner,
                  view: view,
                  onRun: widget.onRun,
                ),
                if (live && meta.cardDone)
                  CardEnd(
                    onNext: () => widget.onRun(RequestBody.next(view!.sid)),
                    onStop: () => widget.onRun(RequestBody.stop(view!.sid)),
                  )
                else if (live)
                  Composer(
                    sid: view!.sid,
                    latest: last,
                    kv: widget.services.kv,
                    enabled: busy == null && !widget.runner.busy,
                    onSend: (t) => widget.onSend(view.sid, t),
                  )
                else
                  Align(
                    alignment: Alignment.centerRight,
                    child: FilledButton(
                      onPressed: () => widget.onRun(RequestBody.sessionStart()),
                      child: const Text('Start session'),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
