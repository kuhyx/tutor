/// Session (curriculum §8): the chat, Card done -> Next / Stop, card actions,
/// Known, stats; wide desktop: all in the bar, the card pane beside the chat
/// (phone: side panel inline); phone keyboard up: no bars, no sidebar.
library;

import 'dart:async';

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
import 'package:tutor/ui/session/gate_flow.dart';
import 'package:tutor/ui/session/session_chat.dart';
import 'package:tutor/ui/session/session_chrome.dart';
import 'package:tutor/ui/session/session_frame.dart';
import 'package:tutor/ui/session/session_layout.dart';
import 'package:tutor/ui/session/session_side.dart';
import 'package:tutor/ui/session/session_subjects.dart';
import 'package:tutor/util/device.dart';

export 'package:tutor/ui/session/session_layout.dart' show kWideLayout;

/// The Session screen.
class SessionScreen extends StatefulWidget {
  /// Creates the screen; [now] is injectable for the stalled pill.
  const new({
    required this.services,
    this.subject,
    this.resume = false,
    this.module,
    this.now,
    this.free = false,
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// Only this subject's live session is followed (null: any).
  final String? subject;

  /// On opening, ask for [subject]'s open session (Home's Continue).
  final bool resume;

  /// On opening, teach this module of [subject] (C4, `/learn/...`); the
  /// worker refusing it replaces this screen with the subject's plan.
  final String? module;

  /// Clock for "stalled".
  final DateTime Function()? now;

  /// Starts (with [resume]) on the free model, not Claude (outage banner).
  final bool free;

  @override
  State<SessionScreen> createState() => _SessionScreenState();
}

class _SessionScreenState extends State<SessionScreen> {
  late final SessionFeed _feed = SessionFeed(
    widget.services.stream,
    subject: widget.subject,
  );
  late final RequestRunner _runner = RequestRunner(
    widget.services.relay,
    stallAfter: sessionStallAfter,
  );
  late final _today = TodayFeed(client: _s.client, rev: _s.rev, kv: _s.kv);
  late final AppLifecycleListener _lifecycle;
  late final VoidCallback _unwatch;
  final _scroll = ScrollController();
  final _scaffold = GlobalKey<ScaffoldState>();
  late final _keyboard = SessionKeyboard(_scaffold);
  late final SessionSubjects _subjectFeed = SessionSubjects(_s, _feed);
  Map<String, SubjectData> get _subjects => _subjectFeed.subjects.value;

  // Next presses refused with nothing to do (Next shakes each time).
  int _refused = 0;

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
    final module = widget.module;
    if (module != null) unawaited(_learn(widget.subject!, module));
    if (module == null && widget.resume) unawaited(_run(_continue()));
    _subjectFeed.start();
  }

  bool _leaving = false; // C4 refused: blank until the plan replaces us

  Future<void> _learn(String subject, String module) async {
    final body = RequestBody.sessionStart(subject: subject, module: module);
    if (!learnRefused(await _run(body)) || !mounted) return;
    setState(() => _leaving = true);
    unawaited(openPlan(context, _s, subject, replace: true));
  }

  @override
  void dispose() {
    _keyboard.dispose();
    _unwatch();
    _lifecycle.dispose();
    unawaited(_subjectFeed.dispose());
    unawaited(_feed.dispose());
    unawaited(_runner.dispose());
    unawaited(_today.dispose());
    _scroll.dispose();
    super.dispose();
  }

  /// Runs [body] through the module gate ([throughGate]: a gated refusal
  /// opens its review, a pass sends [body] again); follows a new session.
  Future<RelayStatus> _run(RequestBody body) async {
    final status = await throughGate(
      context,
      _s,
      () => _send1(body),
      hint: widget.subject ?? _feed.view.value?.meta?.subject,
      now: widget.now ?? DateTime.now,
    );
    // Next with nothing to do now: Next shakes and turns amber.
    if (status case RelayFailed(:final blocked?)
        when !blocked.gated && mounted) {
      setState(() => _refused++);
    }
    return status;
  }

  // One request; every request of this screen says its device.
  Future<RelayStatus> _send1(RequestBody body) async {
    final status = await _runner.run(body.withDevice(deviceName));
    if (status is RelayDone && mounted) {
      _refused = 0;
      final sid = status.data['session'];
      if (sid is String) _feed.follow(sid);
      unawaited(_today.load());
    }
    return status;
  }

  // The review glyph: the same request again reopens what is unpassed.
  void _gate() {
    final last = _runner.lastBody;
    if (last != null) unawaited(_run(last));
  }

  /// Continue (or start) the screen's subject (DOCS-contract §4 `resume`).
  RequestBody _continue() => widget.free
      ? RequestBody.sessionStart(subject: widget.subject, free: true)
      : RequestBody.sessionStart(subject: widget.subject, resume: true);

  Future<bool> _send(String sid, String text) async =>
      await _run(RequestBody.message(sid, text)) is! RelayNotSent;

  @override
  Widget build(BuildContext context) =>
      _leaving ? const Scaffold() : _screen(context);

  Widget _screen(BuildContext context) => ListenableBuilder(
    listenable: Listenable.merge([
      _feed.view,
      _feed.loaded,
      _runner.status,
      _runner.stalled,
      _today.today,
      _subjectFeed.subjects,
    ]),
    builder: (context, _) {
      final view = _feed.view.value;
      final phone = isPhone;
      final keyboard = phone && MediaQuery.viewInsetsOf(context).bottom > 0;
      _keyboard.changed(keyboard: keyboard);
      final meta = view?.meta;
      final subject = _subjects[meta?.subject];
      final mastered = masteredOf(subject, view);
      final card = cardActionsFor(context, _s, subject, view, _run);
      return LayoutBuilder(
        builder: (context, box) {
          final wide = box.maxWidth >= kWideLayout;
          // The phone keeps its layout in landscape too.
          final desk = wide && !phone;
          final chat = SessionChat(
            services: _s,
            feed: _feed,
            view: view,
            today: _today.today.value,
            runner: _runner,
            scroll: _scroll,
            now: widget.now ?? DateTime.now,
            onRun: _run,
            onStart: () => _run(_continue()),
            subject: widget.subject,
            onSend: _send,
            onGate: _gate,
            refused: _refused,
            phone: phone,
            keyboard: keyboard,
            desk: desk,
          );
          final side = SessionSide(
            meta: meta,
            subject: subject,
            mastered: mastered,
            actions: card,
          );
          return SessionFrame(
            scaffoldKey: _scaffold,
            keyboard: keyboard,
            wide: wide,
            desk: desk,
            width: box.maxWidth,
            title: subject?.meta.title,
            meta: meta,
            sid: view?.sid,
            today: _today.today.value,
            now: widget.now,
            card: card,
            mastered: mastered,
            scroll: _scroll,
            chat: chat,
            side: side,
          );
        },
      );
    },
  );
}
