/// One drill: its task and tables, and where the answer is worked out
/// (SQL editor and Run, or a prediction grid and Check), with the result,
/// the mismatches and hints. Two columns on wide windows, two tabs on a
/// phone so the task never pushes the editor off the screen.
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/sql/sql_drafts.dart';
import 'package:tutor/sql/sql_models.dart';
import 'package:tutor/sql/sql_requests.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/fit_layouts.dart';
import 'package:tutor/ui/sql/done_listener.dart';
import 'package:tutor/ui/sql/drill_buttons.dart';
import 'package:tutor/ui/sql/hint_list.dart';
import 'package:tutor/ui/sql/prediction_grid.dart';
import 'package:tutor/ui/sql/problem_cue.dart';
import 'package:tutor/ui/sql/result_view.dart';
import 'package:tutor/ui/sql/sql_editor.dart';
import 'package:tutor/ui/sql/task_view.dart';
import 'package:tutor/widgets/code_symbol_bar.dart';
import 'package:tutor/widgets/content_text.dart';

/// From this width the task and the work sit side by side.
const kSqlTwoPanes = 900.0;

/// The drill screen for [id]; [title] shows while it loads.
class SqlDrillScreen extends StatefulWidget {
  /// Creates the screen.
  const new({
    required this.services,
    required this.id,
    required this.title,
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// Drill id.
  final String id;

  /// Drill title.
  final String title;

  @override
  State<SqlDrillScreen> createState() => _SqlDrillScreenState();
}

class _SqlDrillScreenState extends State<SqlDrillScreen> {
  late final _get = RequestRunner(_s.relay);
  late final _run = RequestRunner(_s.relay);
  late final _hint = RequestRunner(_s.relay, stallAfter: sessionStallAfter);
  late final SqlDrafts _drafts = SqlDrafts(_s.kv);
  late final List<VoidCallback> _unlisten;
  final TextEditingController _sql = TextEditingController();
  Drill? _drill;
  SqlOutcome? _outcome;
  String? _problem;
  Grid _grid = const [];
  final List<String> _hints = [];

  TutorServices get _s => widget.services;

  @override
  void initState() {
    super.initState();
    _unlisten = [
      listenDone(_get, (d) => _parse(() => _drill = parseDrill(d))),
      listenDone(_run, (d) => _parse(() => _outcome = parseOutcome(d))),
      listenDone(_hint, (d) => _parse(() => _hints.add(str(d, 'question')))),
    ];
    unawaited(_load());
  }

  @override
  void dispose() {
    for (final stop in _unlisten) {
      stop();
    }
    _sql.dispose();
    unawaited(_get.dispose());
    unawaited(_run.dispose());
    unawaited(_hint.dispose());
    super.dispose();
  }

  Future<void> _load() async {
    final saved = await _drafts.sql(widget.id);
    final grid = await _drafts.grid(widget.id);
    if (!mounted) return;
    _sql
      ..text = saved
      ..addListener(() => unawaited(_drafts.saveSql(widget.id, _sql.text)));
    setState(() => _grid = grid);
    unawaited(_get.run(sqlGet(widget.id)));
  }

  void _parse(void Function() read) {
    try {
      setState(() {
        _problem = null;
        read();
      });
    } on FormatException catch (e) {
      setState(() => _problem = e.message);
    }
  }

  void _typed(Grid grid) {
    _grid = grid;
    unawaited(_drafts.saveGrid(widget.id, grid));
  }

  @override
  Widget build(BuildContext context) {
    final drill = _drill;
    final wide = MediaQuery.sizeOf(context).width >= kSqlTwoPanes;
    final title = ContentText(drill?.meta.title ?? widget.title);
    if (drill == null) {
      return Scaffold(
        appBar: AppBar(title: title),
        body: PageList(
          children: [
            RequestStatusLine(_get),
            if (_problem != null) problemCue(_problem!),
          ],
        ),
      );
    }
    final task = fitList(
      context,
      padding: const EdgeInsets.all(AppSpacing.md),
      children: taskWidgets(drill),
    );
    final work = ListenableBuilder(
      listenable: _sql,
      builder: (context, _) => WithSymbolBar(
        controller: _sql,
        show: !wide && !drill.meta.predict,
        // Phone: the answer pages; Run/Check and Hint stay above the
        // keyboard.
        child: fitForm(
          context,
          fields: _work(drill),
          bar: [_buttons(drill)],
          // Desktop as before: the buttons under the editor.
          wide: (_) => ListView(
            padding: const EdgeInsets.all(AppSpacing.md),
            keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
            children: [
              ..._work(drill).take(2),
              _buttons(drill),
              ..._work(drill).skip(2),
            ],
          ),
        ),
      ),
    );
    if (wide) {
      return Scaffold(
        appBar: AppBar(title: title),
        body: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1360),
            child: Row(
              children: [
                Expanded(child: task),
                Expanded(child: work),
              ],
            ),
          ),
        ),
      );
    }
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: title,
          bottom: const TabBar(
            tabs: [
              Tab(
                icon: Icon(Icons.description_outlined, semanticLabel: 'Task'),
              ),
              Tab(icon: Icon(Icons.edit_note, semanticLabel: 'Answer')),
            ],
          ),
        ),
        body: SafeArea(child: TabBarView(children: [task, work])),
      ),
    );
  }

  Widget _buttons(Drill drill) {
    final predict = drill.meta.predict;
    return DrillButtons(
      run: _run,
      hint: _hint,
      predict: predict,
      canRun: predict || _sql.text.trim().isNotEmpty,
      onRun: () => unawaited(
        _run.run(
          predict
              ? sqlPredict(widget.id, trimGrid(_grid))
              : sqlRun(widget.id, _sql.text),
        ),
      ),
      onHint: () => unawaited(
        _hint.run(
          sqlHint(
            widget.id,
            history: _hints,
            sql: _sql.text,
            lastResult: _outcome?.hintSlice(),
          ),
        ),
      ),
    );
  }

  List<Widget> _work(Drill drill) {
    final predict = drill.meta.predict;
    final o = _outcome;
    return [
      if (predict)
        PredictionGrid(
          initial: _grid,
          onChanged: _typed,
          marked: {for (final d in o?.diff ?? <CellDiff>[]) (d.row, d.col)},
        )
      else
        SqlEditor(controller: _sql),
      const SizedBox(height: AppSpacing.sm),
      RequestStatusLine(_run),
      RequestStatusLine(_hint),
      if (_problem != null) problemCue(_problem!),
      if (o != null) ResultView(o, key: ObjectKey(o)),
      const SizedBox(height: AppSpacing.md),
      HintList(_hints),
    ];
  }
}
