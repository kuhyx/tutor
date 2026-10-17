/// Session (curriculum §8): the chat from the RTDB projection, answer
/// boxes, busy phase and pending bubble, Card done -> Next card / Stop
/// here, Mark card done, Switch card, mastered list, paused/stalled pills,
/// PC-offline banner. Wide windows get the side panel inline.
library;

import 'dart:async';

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/session/today_header.dart';
import 'package:tutor/ui/limit_switch.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/session/session_actions.dart';
import 'package:tutor/ui/session/session_chat.dart';
import 'package:tutor/ui/session/session_side.dart';
import 'package:tutor/ui/session/session_subjects.dart';
import 'package:tutor/util/device.dart';

/// Width from which the side panel sits beside the chat.
const kWideLayout = 900.0;

/// Widest the chat column gets (prose stays readable on wide windows).
const kChatMaxWidth = 960.0;

/// The side panel's width for a window [width] wide (wide layout only).
double sideWidth(double width) => (width * 0.25).clamp(300, 420);

/// The Session screen.
class SessionScreen extends StatefulWidget {
  /// Creates the screen; [now] is injectable for the stalled pill.
  const new({
    required this.services,
    this.subject,
    this.resume = false,
    this.now,
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// Only this subject's live session is followed (null: any).
  final String? subject;

  /// On opening, ask for [subject]'s open session (Home's Continue).
  final bool resume;

  /// Clock for "stalled".
  final DateTime Function()? now;

  @override
  State<SessionScreen> createState() => _SessionScreenState();
}

class _SessionScreenState extends State<SessionScreen> {
  late final SessionFeed _feed = SessionFeed(
    widget.services.stream,
    subject: widget.subject,
  );
  late final RequestRunner _runner = RequestRunner(widget.services.relay);
  late final TodayFeed _today = TodayFeed(
    client: widget.services.client,
    rev: widget.services.rev,
  );
  late final AppLifecycleListener _lifecycle;
  late final VoidCallback _unwatch;
  final _scroll = ScrollController();
  late final SessionSubjects _subjectFeed = SessionSubjects(_s, _feed);
  Map<String, SubjectData> get _subjects => _subjectFeed.subjects.value;

  TutorServices get _s => widget.services;

  @override
  void initState() {
    super.initState();
    _feed.start();
    _today.start();
    _s.presence.start();
    // Claude out: the model-free drill takes over (also on a Retry).
    _unwatch = switchToDrillOnLimit(this, _s, _runner);
    _lifecycle = AppLifecycleListener(
      onShow: () {
        _feed.start();
        _s.presence.start();
      },
      onHide: () => unawaited(_feed.stop()),
    );
    if (widget.resume) unawaited(_run(_continue()));
    _subjectFeed.start();
  }

  @override
  void dispose() {
    _unwatch();
    _lifecycle.dispose();
    unawaited(_subjectFeed.dispose());
    unawaited(_feed.dispose());
    unawaited(_runner.dispose());
    unawaited(_today.dispose());
    _scroll.dispose();
    super.dispose();
  }

  /// Runs [body]; a result naming a session is followed at once.
  Future<RelayStatus> _run(RequestBody body) async {
    // Every request of this screen says which device it comes from.
    final status = await _runner.run(body.withDevice(deviceName));
    if (status is RelayDone) {
      final sid = status.data['session'];
      if (sid is String && mounted) _feed.follow(sid);
      if (mounted) unawaited(_today.load());
    }
    return status;
  }

  /// Continue (or start) the screen's subject (DOCS-contract §4 `resume`).
  RequestBody _continue() =>
      RequestBody.sessionStart(subject: widget.subject, resume: true);

  Future<bool> _send(String sid, String text) async =>
      await _run(RequestBody.message(sid, text)) is! RelayNotSent;

  Future<void> _switch(String? subjectId) async {
    final subject = _subjects[subjectId];
    if (subject == null) return;
    final card = await pickCard(context, subject);
    if (card != null) {
      await _run(RequestBody.sessionStart(subject: subject.id, card: card));
    }
  }

  // Forwards a wheel over the margins/buttons to the chat (`wheel.js`):
  // anything that scrolls itself (the chat, a text box) claims it first.
  void _wheel(PointerSignalEvent e) {
    if (e is! PointerScrollEvent || !_scroll.hasClients) return;
    GestureBinding.instance.pointerSignalResolver.register(e, (event) {
      final p = _scroll.position;
      final d = (event as PointerScrollEvent).scrollDelta.dy;
      // The chat list is reversed: wheel down = toward offset 0.
      _scroll.jumpTo((p.pixels - d).clamp(0, p.maxScrollExtent));
    });
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: Listenable.merge([
      _feed.view,
      _feed.loaded,
      _runner.status,
      _today.today,
      _subjectFeed.subjects,
    ]),
    builder: (context, _) {
      final view = _feed.view.value;
      final phone = isPhone;
      final keyboard = phone && MediaQuery.viewInsetsOf(context).bottom > 0;
      final meta = view?.meta;
      final subject = _subjects[meta?.subject];
      final live = meta != null && !meta.stopped;
      final side = SessionSide(
        meta: meta,
        subject: subject,
        mastered: <String>{
          ...?subject?.concepts.map((c) => c.name),
          for (final m in view?.messages ?? const <KeyedMessage>[])
            ...m.message.masteredNew,
        }.toList(),
        onSwitch: subject == null ? null : () => _switch(subject.id),
        onMarkDone: live && meta.card != null && !meta.cardDone
            ? () => _run(RequestBody.cardDone(meta.subject, meta.card!.id))
            : null,
        // Card done: CardEnd below offers Stop here instead.
        onStop: live && !meta.cardDone
            ? () => _run(RequestBody.stop(view!.sid))
            : null,
        onEdit: () => openEditor(context, _s, subject: meta?.subject),
        onReport: () =>
            showReport(context, _s, route: '/session', session: view?.sid),
        onHistory: () => openHistory(context, _s),
      );
      final chat = Listener(
        onPointerSignal: _wheel,
        child: SessionChat(
          services: _s,
          feed: _feed,
          view: view,
          today: _today.today.value,
          runner: _runner,
          scroll: _scroll,
          now: widget.now ?? DateTime.now,
          onRun: _run,
          onStart: () => _run(_continue()),
          onSend: _send,
          phone: phone,
          keyboard: keyboard,
        ),
      );
      return LayoutBuilder(
        builder: (context, box) {
          final wide = box.maxWidth >= kWideLayout;
          return Scaffold(
            appBar: AppBar(
              title: Text(subject?.meta.title ?? 'Session'),
              actions: sessionActions(sid: view?.sid, wide: wide),
            ),
            endDrawer: wide ? null : Drawer(child: SafeArea(child: side)),
            body: wide
                ? Row(
                    children: [
                      // The chat keeps a reading width; the panel grows
                      // with the window so long card fronts wrap, not clip.
                      Expanded(
                        child: Align(
                          alignment: Alignment.topCenter,
                          child: ConstrainedBox(
                            constraints: const BoxConstraints(
                              maxWidth: kChatMaxWidth,
                            ),
                            child: chat,
                          ),
                        ),
                      ),
                      const VerticalDivider(width: 1),
                      SizedBox(width: sideWidth(box.maxWidth), child: side),
                    ],
                  )
                : chat,
          );
        },
      );
    },
  );
}
