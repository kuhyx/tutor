import 'dart:async';

import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/mock/mock_links.dart';
import 'package:tutor/mock/mock_models.dart';
import 'package:tutor/mock/mock_nav_bar.dart';
import 'package:tutor/mock/mock_requests.dart';
import 'package:tutor/mock/mock_result_screen.dart';
import 'package:tutor/mock/mock_session.dart';
import 'package:tutor/mock/mock_task_views.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/layout.dart';
import 'package:tutor/ui/sql/done_listener.dart';

/// Retry grading every this many seconds once time is up.
const _retryEvery = 10;

/// The running test: clock, task chips, the task, Finish.
class MockTestScreen extends StatefulWidget {
  /// Creates the screen over a started [session].
  const new({
    required this.services,
    required this.session,
    required this.links,
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// The test.
  final MockSession session;

  /// Where the result's review buttons go.
  final MockLinks links;

  @override
  State<MockTestScreen> createState() => _MockTestScreenState();
}

class _MockTestScreenState extends State<MockTestScreen> {
  late final _run = RequestRunner(widget.services.relay);
  late final _finish = RequestRunner(widget.services.relay);
  final _editors = <String, TextEditingController>{};
  final _outs = <String, MockRun>{};
  late final List<VoidCallback> _unlisten;
  late final Timer _tick;
  String _runTask = '';
  bool _ending = false;
  bool _unsent = false;
  bool _notes = true;
  int _secs = 0;

  MockSession get _s => widget.session;

  @override
  void initState() {
    super.initState();
    _s.addListener(_redraw);
    _unlisten = [
      listenDone(_run, (d) {
        try {
          setState(() => _outs[_runTask] = parseRun(d));
        } on FormatException {
          setState(() => _outs.remove(_runTask));
        }
      }),
      listenDone(_finish, (d) {
        _s.finished(d);
        _toResult();
      }),
    ];
    _tick = Timer.periodic(const Duration(seconds: 1), (_) => _clock());
    if (_s.remaining == Duration.zero) unawaited(Future.microtask(_end));
  }

  @override
  void dispose() {
    _tick.cancel();
    _s.removeListener(_redraw);
    for (final stop in _unlisten) {
      stop();
    }
    for (final c in _editors.values) {
      c.dispose();
    }
    unawaited(_run.dispose());
    unawaited(_finish.dispose());
    super.dispose();
  }

  void _redraw() {
    if (mounted) setState(() {});
  }

  void _clock() {
    setState(() => _secs++);
    if (_s.remaining == Duration.zero && _secs % _retryEvery == 0) {
      unawaited(_end());
    }
  }

  void _toResult() {
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute<void>(
        builder: (_) => MockResultScreen(
          services: widget.services,
          session: _s,
          links: widget.links,
        ),
      ),
    );
  }

  Future<void> _end() async {
    if (_ending) return;
    _ending = true;
    final sent = await _s.settle();
    if (!mounted) return;
    setState(() => _unsent = !sent);
    if (sent) await _finish.run(mockFinish(_s.paper.mockId));
    _ending = false;
  }

  Future<void> _confirm() async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        content: Text(
          '${_s.paper.tasks.where((t) => _s.isSubmitted(t.id)).length}'
          '/${_s.paper.tasks.length}',
        ),
        actions: [
          IconButton(
            key: const ValueKey('cancel'),
            onPressed: () => Navigator.pop(c, false),
            icon: const Icon(Icons.close, semanticLabel: 'Cancel'),
          ),
          IconButton(
            key: const ValueKey('confirm'),
            onPressed: () => Navigator.pop(c, true),
            icon: const Icon(Icons.flag, semanticLabel: 'Finish'),
          ),
        ],
      ),
    );
    if (yes ?? false) await _end();
  }

  TextEditingController _editor(MockTask t) => _editors.putIfAbsent(t.id, () {
    final c = TextEditingController(text: _s.answers[t.id] ?? t.starter);
    c.addListener(() {
      if (c.text != (_s.answers[t.id] ?? t.starter)) {
        _s.update(id: t.id, text: c.text);
      }
    });
    return c;
  });

  String get _clockText {
    final r = _s.remaining;
    final sec = r.inSeconds % 60;
    return '${r.inMinutes}:${sec.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    final task = _s.paper.tasks[_s.index];
    final editor = task.section.typed ? _editor(task) : null;
    final typing =
        isCompact(context) && MediaQuery.viewInsetsOf(context).bottom > 0;
    return Scaffold(
      appBar: AppBar(
        title: Text(_clockText, key: const ValueKey('clock')),
        actions: [
          IconButton(
            key: const ValueKey('finish'),
            onPressed: _confirm,
            icon: const Icon(Icons.flag_outlined, semanticLabel: 'Finish'),
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Phone, typing: the task and its keys get the room; the
            // task chips and notes return with the keyboard down.
            if (!typing) MockNavBar(_s),
            if (_notes && !typing && _s.paper.notes.isNotEmpty)
              ListTile(
                dense: true,
                title: Text(_s.paper.notes.join(' ')),
                trailing: IconButton(
                  key: const ValueKey('notes-close'),
                  onPressed: () => setState(() => _notes = false),
                  icon: const Icon(Icons.close, semanticLabel: 'Dismiss'),
                ),
              ),
            if (_unsent) const Icon(Icons.cloud_off, key: ValueKey('unsent')),
            RequestStatusLine(_finish),
            Expanded(
              child: mockTaskBody(
                session: _s,
                task: task,
                editor: editor,
                out: _outs[task.id],
                runLine: RequestStatusLine(_run),
                onRun: editor == null
                    ? null
                    : () {
                        _runTask = task.id;
                        unawaited(
                          _run.run(
                            mockRun(_s.paper.mockId, task.id, editor.text),
                          ),
                        );
                      },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
