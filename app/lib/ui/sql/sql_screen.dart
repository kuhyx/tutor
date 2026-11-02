/// SQL practice: the drills grouped by topic, a New drill button per topic.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/sql/sql_models.dart';
import 'package:tutor/sql/sql_requests.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/sql/done_listener.dart';
import 'package:tutor/ui/sql/drill_screen.dart';
import 'package:tutor/ui/sql/lesson_screen.dart';

/// The topic list.
class SqlPracticeScreen extends StatefulWidget {
  /// Creates the screen.
  const new({required this.services, super.key});

  /// Services.
  final TutorServices services;

  @override
  State<SqlPracticeScreen> createState() => _SqlPracticeScreenState();
}

class _SqlPracticeScreenState extends State<SqlPracticeScreen> {
  late final _list = RequestRunner(widget.services.relay);
  late final _generate = RequestRunner(
    widget.services.relay,
    stallAfter: sessionStallAfter,
  );
  late final List<VoidCallback> _unlisten;
  DrillList? _drills;
  String? _problem;

  void _read(void Function() read) {
    try {
      setState(() {
        _problem = null;
        read();
      });
    } on FormatException catch (e) {
      setState(() => _problem = e.message);
    }
  }

  @override
  void initState() {
    super.initState();
    _unlisten = [
      listenDone(_list, (d) => _read(() => _drills = parseDrillList(d))),
      listenDone(
        _generate,
        (d) => _read(
          () => unawaited(
            _open(
              parseDrillList({
                'drills': [d],
              }).drills.single,
            ),
          ),
        ),
      ),
    ];
    unawaited(_list.run(sqlList()));
  }

  @override
  void dispose() {
    for (final stop in _unlisten) {
      stop();
    }
    unawaited(_list.dispose());
    unawaited(_generate.dispose());
    super.dispose();
  }

  Future<void> _lesson(String topic) => Navigator.of(context).push<void>(
    MaterialPageRoute(
      builder: (_) => SqlLessonScreen(services: widget.services, topic: topic),
    ),
  );

  Future<void> _open(DrillMeta drill) => Navigator.of(context)
      .push<void>(
        MaterialPageRoute(
          builder: (_) => SqlDrillScreen(
            services: widget.services,
            id: drill.id,
            title: drill.title,
          ),
        ),
      )
      .then((_) => _list.run(sqlList()));

  @override
  Widget build(BuildContext context) {
    final drills = _drills;
    final topics = <String>{
      ...?drills?.topics,
      for (final d in drills?.drills ?? <DrillMeta>[]) d.topic,
    }.toList();
    return Scaffold(
      appBar: AppBar(
        title: const Icon(Icons.storage_outlined, semanticLabel: 'SQL'),
      ),
      body: PageList(
        children: [
          RequestStatusLine(_list),
          RequestStatusLine(_generate),
          if (_problem != null) Text(_problem!),
          RunnerBuilder(
            _generate,
            (_) => _generate.busy
                ? const LinearProgressIndicator()
                : const SizedBox.shrink(),
          ),
          for (final topic in topics) ..._topic(topic, drills),
        ],
      ),
    );
  }

  List<Widget> _topic(String topic, DrillList? drills) => [
    ListTile(
      key: ValueKey('lesson-$topic'),
      leading: const Icon(Icons.school_outlined, semanticLabel: 'Lesson'),
      title: Text(topic, style: Theme.of(context).textTheme.titleMedium),
      onTap: () => unawaited(_lesson(topic)),
      trailing: RunnerBuilder(
        _generate,
        (_) => IconButton(
          key: ValueKey('new-drill-$topic'),
          onPressed: _generate.busy
              ? null
              : () => unawaited(_generate.run(sqlGenerate(topic))),
          icon: const Icon(Icons.add, semanticLabel: 'New drill'),
        ),
      ),
    ),
    for (final d in drills?.drills ?? <DrillMeta>[])
      if (d.topic == topic)
        ListTile(
          leading: Icon(
            d.predict ? Icons.visibility_outlined : Icons.edit_note,
            semanticLabel: d.predict ? 'Predict' : 'Write',
          ),
          title: Text(d.title),
          trailing: d.generated
              ? const Icon(Icons.auto_awesome, semanticLabel: 'Generated')
              : null,
          onTap: () => unawaited(_open(d)),
        ),
  ];
}
