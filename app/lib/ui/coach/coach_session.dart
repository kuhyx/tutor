/// One coach session on one screen; widgets listen, it never builds UI.
library;

// Widgets read this state directly; the member names say what they hold.
// ignore_for_file: public_member_api_docs

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/coach/coach_drafts.dart';
import 'package:tutor/coach/coach_models.dart';
import 'package:tutor/coach/coach_requests.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/sql/lesson_models.dart';
import 'package:tutor/ui/sql/done_listener.dart';

/// State and actions of the coach screen: problem, chat, code, requests.
class CoachSession extends ChangeNotifier {
  /// Opens with `open`; a resume passes `resumeId` so the stored copy of the
  /// chat shows before the worker answers.
  new(this.services, {required this.open, this.resumeId}) {
    _stops = [
      listenDone(opener, _onOpened),
      listenDone(turns, _onTurn),
      listenDone(runs, _onRun),
    ];
    opener.status.addListener(_onOpenStatus);
    code.addListener(_saveCode);
  }

  final TutorServices services;
  final RequestBody open;
  final String? resumeId;
  late final opener = RequestRunner(services.relay);
  late final turns = RequestRunner(
    services.relay,
    stallAfter: sessionStallAfter,
  );
  late final runs = RequestRunner(services.relay);
  final answer = TextEditingController();
  final code = TextEditingController();
  final List<Bubble> thread = [];
  Opened? opened;
  CoachState state = openState;
  String lang = defaultCoachLang;
  String? pin;
  String? note;
  List<String> choices = const [];
  RunReport? report;
  String? summaryMd;
  String? problem;
  bool needsStatement = false;

  late final CoachDrafts _drafts = CoachDrafts(services.kv);
  late final List<VoidCallback> _stops;
  bool _loadingCode = false;

  /// Sends `lc_open`, after showing the stored chat of a resume.
  Future<void> start() async {
    final id = resumeId;
    if (id != null) {
      thread.addAll(await _drafts.thread(id));
      notifyListeners();
    }
    unawaited(opener.run(open));
  }

  /// Opens again with a pasted statement (premium or unknown slug).
  void pasteStatement(String title, String statement) {
    needsStatement = false;
    notifyListeners();
    final name = title.trim();
    unawaited(
      opener.run(
        lcOpen(statement: statement, title: name.isEmpty ? null : name),
      ),
    );
  }

  void _onOpenStatus() {
    final s = opener.status.value;
    if (s is RelayFailed && s.reason == 'paste_statement') {
      needsStatement = true;
      notifyListeners();
    }
  }

  void _guard(void Function() read) {
    try {
      problem = null;
      read();
    } on FormatException catch (e) {
      problem = e.message;
    }
    notifyListeners();
  }

  void _onOpened(Map<String, dynamic> data) => _guard(() {
    final o = parseOpened(data);
    opened = o;
    state = o.state ?? state;
    thread
      ..clear()
      ..addAll(
        o.thread ??
            [if (o.replyMd != null) (mine: false, md: o.replyMd, grid: null)],
      );
    _repin();
    unawaited(_saveThread());
    unawaited(_loadLang(o));
  });

  Future<void> _loadLang(Opened o) async {
    final saved = await _drafts.lang(o.slug);
    await _setLang(o.langs.contains(saved) ? saved : o.lang);
  }

  Future<void> _setLang(String next) async {
    final o = opened;
    if (o == null) return;
    lang = next;
    _loadingCode = true;
    code.text = await _drafts.code(o.slug, next) ?? o.starter[next] ?? '';
    _loadingCode = false;
    report = null;
    notifyListeners();
  }

  /// Switches the editor to `next`, with its draft or starter code.
  Future<void> setLang(String next) async {
    final o = opened;
    if (o != null) await _drafts.saveLang(o.slug, next);
    await _setLang(next);
  }

  void _saveCode() {
    final o = opened;
    if (o != null && !_loadingCode) {
      unawaited(_drafts.saveCode(o.slug, lang, code.text));
    }
  }

  Future<void> _saveThread() {
    final id = opened?.lcId;
    return id == null ? Future.value() : _drafts.saveThread(id, thread);
  }

  void _repin() {
    for (final b in thread.reversed) {
      final found = b.mine || b.md == null ? null : extractPin(b.md!);
      if (found != null) {
        pin = found;
        return;
      }
    }
  }

  /// Drops the pinned snippet.
  void unpin() {
    pin = null;
    notifyListeners();
  }

  bool get canSend => opened != null && turns.canSend;

  /// Sends `text` to the coach; `solved` claims the problem is solved.
  void send(String text, {bool solved = false}) {
    final id = opened?.lcId;
    final t = text.trim();
    if (id == null || t.isEmpty || t.length > coachMaxText) return;
    thread.add((mine: true, md: t, grid: null));
    note = null;
    choices = const [];
    notifyListeners();
    unawaited(_saveThread());
    unawaited(turns.run(lcTurn(id, t, solved: solved)));
  }

  /// Runs the editor's code against the statement examples.
  void run() {
    final id = opened?.lcId;
    if (id != null && code.text.trim().isNotEmpty) {
      unawaited(runs.run(lcRun(id, lang: lang, code: code.text)));
    }
  }

  void _onTurn(Map<String, dynamic> data) => _guard(() {
    final t = parseCoachTurn(data);
    state = t.state ?? state;
    note = t.note ?? t.exit?.missing;
    choices = t.choices;
    summaryMd = t.exit?.summaryMd ?? summaryMd;
    for (final md in [t.replyMd, t.exit?.summaryMd]) {
      if (md != null) thread.add((mine: false, md: md, grid: null));
    }
    _repin();
    unawaited(_saveThread());
  });

  void _onRun(Map<String, dynamic> data) => _guard(() {
    final r = parseRunReport(data);
    report = r;
    state = r.state ?? state;
    note = r.held ? r.note : null;
  });

  @override
  void dispose() {
    for (final stop in _stops) {
      stop();
    }
    opener.status.removeListener(_onOpenStatus);
    code.removeListener(_saveCode);
    answer.dispose();
    code.dispose();
    unawaited(opener.dispose());
    unawaited(turns.dispose());
    unawaited(runs.dispose());
    super.dispose();
  }
}
