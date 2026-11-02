/// A guided lesson on one topic: the tables stay pinned while the tutor's
/// questions and feedback scroll as a chat and the learner answers in free
/// text (prediction and reasoning).
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/sql/lesson_models.dart';
import 'package:tutor/sql/sql_drafts.dart';
import 'package:tutor/sql/sql_models.dart';
import 'package:tutor/sql/sql_requests.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/sql/done_listener.dart';
import 'package:tutor/ui/sql/drill_screen.dart';
import 'package:tutor/ui/sql/lesson_parts.dart';
import 'package:tutor/ui/sql/task_view.dart';

/// The lesson for [topic]; it resumes the one saved on this install.
class SqlLessonScreen extends StatefulWidget {
  /// Creates the screen.
  const new({required this.services, required this.topic, super.key});

  /// Services.
  final TutorServices services;

  /// Topic name.
  final String topic;

  @override
  State<SqlLessonScreen> createState() => _SqlLessonScreenState();
}

class _SqlLessonScreenState extends State<SqlLessonScreen>
    with WidgetsBindingObserver {
  late final _turns = RequestRunner(
    widget.services.relay,
    stallAfter: sessionStallAfter,
  );
  late final _drafts = SqlDrafts(widget.services.kv);
  final _answer = TextEditingController();
  final _focus = FocusNode();
  final _scroll = ScrollController();
  late final List<VoidCallback> _unlisten;
  final List<Bubble> _thread = [];
  List<SqlTable> _tables = const [];
  LessonTurn? _turn;
  String? _lessonId;
  String? _problem;
  bool _tablesOpen = true;
  bool _resuming = false;

  String get _topic => widget.topic;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _focus.addListener(_onFocus);
    _turns.status.addListener(_onStatus);
    _unlisten = [listenDone(_turns, _apply)];
    unawaited(_start());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    for (final stop in _unlisten) {
      stop();
    }
    _turns.status.removeListener(_onStatus);
    _focus
      ..removeListener(_onFocus)
      ..dispose();
    _answer.dispose();
    _scroll.dispose();
    unawaited(_turns.dispose());
    super.dispose();
  }

  @override
  void didChangeMetrics() => _toEnd();

  void _onFocus() {
    if (_focus.hasFocus) setState(() => _tablesOpen = false);
    _toEnd();
  }

  void _toEnd() => WidgetsBinding.instance.addPostFrameCallback((_) {
    if (_scroll.hasClients) _scroll.jumpTo(_scroll.position.maxScrollExtent);
  });

  Future<void> _start() async {
    final saved = await _drafts.lesson(_topic);
    if (!mounted) return;
    _resuming = saved != null;
    unawaited(_turns.run(sqlLessonTurn(_topic, lessonId: saved)));
  }

  void _onStatus() {
    final s = _turns.status.value;
    if (_resuming && s is RelayFailed && s.code == 'bad_request') {
      _resuming = false;
      unawaited(_drafts.forgetLesson(_topic));
      unawaited(_turns.run(sqlLessonTurn(_topic)));
    }
  }

  void _apply(Map<String, dynamic> data) {
    try {
      final t = parseLessonTurn(data);
      _resuming = false;
      unawaited(_drafts.saveLesson(_topic, t.lessonId));
      setState(() {
        _problem = null;
        _turn = t;
        _lessonId = t.lessonId;
        _tables = t.tables ?? _tables;
        _thread.addAll([
          if (t.feedbackMd != null) (mine: false, md: t.feedbackMd, grid: null),
          if (t.result != null) (mine: false, md: null, grid: t.result),
          if (t.summaryMd != null) (mine: false, md: t.summaryMd, grid: null),
          if (t.questionMd != null) (mine: false, md: t.questionMd, grid: null),
        ]);
      });
      _toEnd();
    } on FormatException catch (e) {
      setState(() => _problem = e.message);
    }
  }

  void _send() {
    final text = _answer.text.trim();
    final id = _lessonId;
    if (text.isEmpty || id == null) return;
    setState(() => _thread.add((mine: true, md: text, grid: null)));
    _answer.clear();
    _toEnd();
    unawaited(_turns.run(sqlLessonTurn(_topic, lessonId: id, answer: text)));
  }

  Future<void> _next(String topic) => Navigator.of(context).pushReplacement(
    MaterialPageRoute<void>(
      builder: (_) => SqlLessonScreen(services: widget.services, topic: topic),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= kSqlTwoPanes;
    final chat = _chat();
    final body = !wide
        ? Column(
            children: [
              if (_tables.isNotEmpty)
                PinnedTables(
                  tables: _tables,
                  open: _tablesOpen,
                  onToggle: () => setState(() => _tablesOpen = !_tablesOpen),
                ),
              const Divider(height: 1),
              Expanded(child: chat),
            ],
          )
        : Align(
            alignment: Alignment.topCenter,
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1360),
              child: Row(
                children: [
                  Expanded(
                    flex: 2,
                    child: ListView(
                      key: const ValueKey('tables-pane'),
                      padding: const EdgeInsets.all(AppSpacing.md),
                      children: tableWidgets(_tables),
                    ),
                  ),
                  const VerticalDivider(width: 1),
                  Expanded(flex: 3, child: chat),
                ],
              ),
            ),
          );
    return Scaffold(
      appBar: AppBar(title: Text(_topic)),
      body: SafeArea(child: body),
    );
  }

  Widget _chat() {
    final turn = _turn;
    final next = nextLessonTopic(_topic);
    return Column(
      children: [
        if (turn != null)
          ListTile(
            dense: true,
            leading: Icon(
              turn.check ? Icons.quiz_outlined : Icons.school_outlined,
              semanticLabel: turn.check ? 'Check' : 'Lesson',
            ),
            title: Text(turn.concept),
            trailing: Text('${turn.index + 1}/${turn.total}'),
          ),
        Expanded(
          child: ListView(
            controller: _scroll,
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              for (final b in _thread) BubbleView(b),
              if (_problem != null) Text(_problem!),
            ],
          ),
        ),
        RunnerBuilder(
          _turns,
          (_) => _turns.busy
              ? const LinearProgressIndicator()
              : const SizedBox.shrink(),
        ),
        RequestStatusLine(_turns),
        if (turn?.done ?? false)
          LessonEnd(next: next, onNext: () => unawaited(_next(next!)))
        else
          RunnerBuilder(
            _turns,
            (_) => AnswerBox(
              controller: _answer,
              focus: _focus,
              canSend: _turns.canSend && _lessonId != null,
              onSend: _send,
            ),
          ),
      ],
    );
  }
}
