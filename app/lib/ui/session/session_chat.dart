/// The Session's chat column: status line with paused/stalled pills, the
/// messages, the pending learner bubble and busy phase, then Card done
/// (Next card / Stop here), the composer, or Start.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/session/collapsed_tile.dart';
import 'package:tutor/ui/session/composer.dart';
import 'package:tutor/ui/session/message_tile.dart';
import 'package:tutor/ui/session/session_bits.dart';
import 'package:tutor/ui/session/session_header.dart';

/// The chat column.
class SessionChat extends StatefulWidget {
  /// Creates the column.
  const new({
    required this.services,
    required this.feed,
    required this.view,
    required this.today,
    required this.runner,
    required this.scroll,
    required this.now,
    required this.onRun,
    required this.onStart,
    required this.onSend,
    this.phone = false,
    this.keyboard = false,
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// The feed (for "loaded").
  final SessionFeed feed;

  /// Session on screen.
  final SessionView? view;

  /// `stats.today` for the header (null until read).
  final Today? today;

  /// Request runner.
  final RequestRunner runner;

  /// Chat scroller.
  final ScrollController scroll;

  /// Clock.
  final DateTime Function() now;

  /// Runs a request.
  final Future<RelayStatus> Function(RequestBody body) onRun;

  /// Start session (or continue the subject's open one).
  final VoidCallback onStart;

  /// Sends a learner message.
  final Future<bool> Function(String sid, String text) onSend;

  /// The Android app (step-through composer).
  final bool phone;

  /// The phone keyboard is open: no header lines, the latest tutor message
  /// folded to its last line, chat and composer text at 85%.
  final bool keyboard;

  @override
  State<SessionChat> createState() => _SessionChatState();
}

class _SessionChatState extends State<SessionChat> {
  int _count = -1;

  // New messages scroll to the bottom (offset 0: the list is reversed).
  void _follow(int count) {
    if (count == _count) return;
    _count = count;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final s = widget.scroll;
      if (s.hasClients) s.jumpTo(0);
    });
  }

  @override
  Widget build(BuildContext context) {
    final view = widget.view;
    final meta = view?.meta;
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
    final empty = view == null || (messages.isEmpty && busy == null);
    // Nothing shown yet but something is coming: a request or a first turn.
    final waiting =
        widget.runner.busy || (view != null && !(meta?.stopped ?? false));
    final mq = MediaQuery.of(context);
    final chat = LayoutBuilder(
      builder: (context, box) => Column(
        children: [
          if (meta != null)
            SessionHeader(
              meta: meta,
              today: widget.today,
              nowMs: widget.now().millisecondsSinceEpoch,
              live: live,
              compact: widget.keyboard,
            ),
          PcOfflineBanner(widget.services.presence.state),
          Expanded(
            child: empty
                ? NoChat(
                    waiting: waiting,
                    loaded: widget.feed.loaded.value || view != null,
                  )
                // Reversed (offset 0 = newest: late pictures above never push
                // the bottom away); ONE SelectionArea: copies as one text.
                : SelectionArea(
                    child: ListView(
                      controller: widget.scroll,
                      reverse: true,
                      padding: const EdgeInsets.all(AppSpacing.md),
                      children: [
                        for (final (i, m) in messages.indexed)
                          _tile(
                            m,
                            i == messages.length - 1,
                            boxes: boxes,
                            sid: view.sid,
                          ),
                        if (busy != null && (busy.text ?? '').isNotEmpty)
                          MessageTile(
                            message: Message(role: 'learner', text: busy.text!),
                            pending: true,
                          ),
                        if (busy != null) Text(phaseText(busy.phase)),
                      ].reversed.toList(),
                    ),
                  ),
          ),
          const Divider(height: 1),
          ConstrainedBox(
            constraints: BoxConstraints(maxHeight: box.maxHeight * _share),
            child: sessionPanel(
              phone: widget.phone,
              Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  NotLiveStatus(
                    services: widget.services,
                    runner: widget.runner,
                    view: view,
                    subject: meta?.subject,
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
                      phone: widget.phone,
                    )
                  else
                    Align(
                      alignment: Alignment.centerRight,
                      child: FilledButton(
                        onPressed: widget.onStart,
                        child: const Text('Start session'),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
    // Same tree keyboard open or shut: a new root would drop focus.
    return MediaQuery(
      data: mq.copyWith(
        textScaler: widget.keyboard
            ? TextScaler.linear(mq.textScaler.scale(1) * 0.85)
            : mq.textScaler,
      ),
      child: chat,
    );
  }

  // The height share the composer may take (the chat stays the scroller).
  double get _share => widget.keyboard ? 0.7 : (widget.phone ? 0.5 : 0.4);

  Widget _tile(
    KeyedMessage m,
    bool latest, {
    required bool boxes,
    required String sid,
  }) {
    final tutor = m.message.role == 'tutor';
    final tile = MessageTile(
      message: m.message,
      questionsAsBoxes: boxes && latest,
      onReport: tutor
          ? () => showReport(
              context,
              widget.services,
              route: '/session',
              session: sid,
              msg: m.key,
              preview: m.message.text,
            )
          : null,
    );
    return widget.keyboard && latest && tutor
        ? CollapsedTile(message: m.message, full: tile)
        : tile;
  }
}
