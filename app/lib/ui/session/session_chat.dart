/// The Session's chat column: status line with paused/stalled pills, the
/// messages, the pending learner bubble and busy phase, then Card done
/// (Next card / Stop here) above the composer, or Start.
library;

import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/fit_pages.dart';
import 'package:tutor/ui/session/composer.dart';
import 'package:tutor/ui/session/session_bits.dart';
import 'package:tutor/ui/session/session_header.dart';
import 'package:tutor/ui/session/session_turns.dart';

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
    this.subject,
    this.phone = false,
    this.keyboard = false,
    super.key,
  });

  /// The screen's subject (when no session shows yet).
  final String? subject;

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
  final _pages = FitPageController();

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  // New messages scroll to the bottom (offset 0: the list is reversed).
  void _follow(int count) {
    if (count == _count) return;
    _count = count;
    _pages.toLast();
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
                : SelectionArea(
                    child: ChatTurns(
                      messages: messages,
                      boxes: boxes,
                      busy: busy,
                      view: view,
                      services: widget.services,
                      keyboard: widget.keyboard,
                      pages: _pages,
                      scroll: widget.scroll,
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
                    subject: meta?.subject ?? widget.subject,
                    onRun: widget.onRun,
                  ),
                  // Card done: Next card / Stop here, and the composer
                  // stays for follow-up questions (kuhy, 2026-10-20).
                  if (live && meta.cardDone)
                    CardEnd(
                      onNext: () => widget.onRun(RequestBody.next(view!.sid)),
                      onStop: () => widget.onRun(RequestBody.stop(view!.sid)),
                    ),
                  if (live)
                    Composer(
                      sid: view!.sid,
                      latest: last,
                      kv: widget.services.kv,
                      // A lost reply must not block Send forever: once the
                      // runner is stalled the learner may send again.
                      enabled:
                          widget.runner.stalled.value ||
                          (busy == null && !widget.runner.busy),
                      onSend: (t) => widget.onSend(view.sid, t),
                      phone: widget.phone,
                    )
                  // A block's call to action replaces Start (same result).
                  else if (!(widget.runner.status.value?.blocks ?? false))
                    StartButton(onStart: widget.onStart),
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
}
