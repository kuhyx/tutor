/// Problem coach start: paste a LeetCode URL or slug, due cold re-tests,
/// recent sessions to resume, and the clusters.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/coach/coach_models.dart';
import 'package:tutor/coach/coach_requests.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/coach/coach_screen.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/sql/done_listener.dart';

/// The picker.
class CoachPickerScreen extends StatefulWidget {
  /// Creates the screen.
  const new({required this.services, super.key});

  /// Services.
  final TutorServices services;

  @override
  State<CoachPickerScreen> createState() => _CoachPickerScreenState();
}

class _CoachPickerScreenState extends State<CoachPickerScreen> {
  late final _list = RequestRunner(widget.services.relay);
  final _input = TextEditingController();
  late final VoidCallback _unlisten;
  CoachList? _lists;
  String? _problem;
  bool _bad = false;

  @override
  void initState() {
    super.initState();
    _unlisten = listenDone(_list, _apply);
    unawaited(_list.run(lcList()));
  }

  @override
  void dispose() {
    _unlisten();
    _input.dispose();
    unawaited(_list.dispose());
    super.dispose();
  }

  void _apply(Map<String, dynamic> data) {
    try {
      setState(() {
        _problem = null;
        _lists = parseCoachList(data);
      });
    } on FormatException catch (e) {
      setState(() => _problem = e.message);
    }
  }

  Future<void> _open(RequestBody body, {String? title}) => Navigator.of(context)
      .push<void>(
        MaterialPageRoute(
          builder: (_) =>
              CoachScreen(services: widget.services, open: body, title: title),
        ),
      )
      .then((_) => _list.run(lcList()));

  void _go() {
    final slug = slugFromInput(_input.text);
    setState(() => _bad = slug == null);
    if (slug != null) unawaited(_open(lcOpen(problem: slug), title: slug));
  }

  @override
  Widget build(BuildContext context) {
    final lists = _lists;
    return Scaffold(
      appBar: AppBar(
        title: const Icon(Icons.psychology_outlined, semanticLabel: 'Coach'),
      ),
      body: PageList(
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  key: const ValueKey('problem'),
                  controller: _input,
                  autocorrect: false,
                  textInputAction: TextInputAction.go,
                  onSubmitted: (_) => _go(),
                  decoration: InputDecoration(
                    prefixIcon: const Icon(Icons.link),
                    border: const OutlineInputBorder(),
                    errorText: _bad ? '' : null,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filled(
                key: const ValueKey('go'),
                onPressed: _go,
                icon: const Icon(Icons.arrow_forward, semanticLabel: 'Start'),
              ),
            ],
          ),
          RequestStatusLine(_list),
          if (_problem != null) Text(_problem!),
          if (lists != null) ..._sections(lists),
        ],
      ),
    );
  }

  List<Widget> _sections(CoachList lists) => [
    if (lists.due.isNotEmpty) ...[
      ListTile(
        leading: const Icon(Icons.event_repeat, semanticLabel: 'Re-test'),
        title: Text(AppLocalizations.of(context).retestNoSubmit),
      ),
      for (final d in lists.due)
        ListTile(
          title: Text(d.title),
          onTap: () =>
              unawaited(_open(lcOpen(problem: d.slug), title: d.title)),
        ),
    ],
    for (final r in lists.recent)
      ListTile(
        leading: Icon(
          r.phase == 'done' ? Icons.check_circle_outline : Icons.history,
          semanticLabel: r.phase,
        ),
        title: Text(r.title),
        onTap: () => unawaited(_open(lcOpen(lcId: r.lcId), title: r.title)),
      ),
    for (final c in lists.clusters)
      ExpansionTile(
        title: Text(c.name),
        children: [
          for (final slug in c.problems)
            ListTile(
              title: Text(slug),
              onTap: () => unawaited(_open(lcOpen(problem: slug), title: slug)),
            ),
        ],
      ),
  ];
}
