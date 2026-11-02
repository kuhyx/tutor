import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/coach/coach_models.dart';
import 'package:tutor/coach/coach_requests.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/sql/data_grid.dart';
import 'package:tutor/ui/sql/done_listener.dart';
import 'package:tutor/ui/sql/rich_md.dart';

/// After the exit: the summary table, the cards made (tutor FSRS and Anki),
/// and the toolbox entries the coach proposes, each to confirm or skip.
class CoachPostMortemScreen extends StatefulWidget {
  /// Creates the screen and asks for the cards.
  const new({
    required this.services,
    required this.lcId,
    this.summaryMd,
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// The session.
  final String lcId;

  /// The summary table of the exit, if any.
  final String? summaryMd;

  @override
  State<CoachPostMortemScreen> createState() => _PostMortemState();
}

class _PostMortemState extends State<CoachPostMortemScreen> {
  late final _cards = RequestRunner(
    widget.services.relay,
    stallAfter: sessionStallAfter,
  );
  late final VoidCallback _unlisten;
  CoachCards? _result;
  final Set<String> _skipped = {};
  String? _problem;

  @override
  void initState() {
    super.initState();
    _unlisten = listenDone(_cards, _apply);
    unawaited(_cards.run(lcCards(widget.lcId, const [])));
  }

  @override
  void dispose() {
    _unlisten();
    unawaited(_cards.dispose());
    super.dispose();
  }

  void _apply(Map<String, dynamic> data) {
    try {
      setState(() {
        _problem = null;
        _result = parseCoachCards(data);
        _skipped.clear();
      });
    } on FormatException catch (e) {
      setState(() => _problem = e.message);
    }
  }

  void _confirm(List<ToolboxEntry> proposals) => unawaited(
    _cards.run(
      lcCards(widget.lcId, [
        for (final p in proposals)
          if (!_skipped.contains(p.name)) p,
      ]),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final r = _result;
    final summary = widget.summaryMd;
    return Scaffold(
      appBar: AppBar(
        title: const Icon(Icons.style_outlined, semanticLabel: 'Post-mortem'),
      ),
      body: PageList(
        children: [
          if (summary != null) RichMd(summary),
          RequestStatusLine(_cards),
          RunnerBuilder(
            _cards,
            (_) => _cards.busy
                ? const LinearProgressIndicator()
                : const SizedBox.shrink(),
          ),
          if (_problem != null) Text(_problem!),
          if (r != null) ..._body(r),
        ],
      ),
    );
  }

  List<Widget> _body(CoachCards r) => [
    for (final c in r.cards)
      ListTile(
        leading: Icon(
          c.isNew ? Icons.fiber_new_outlined : Icons.style_outlined,
          semanticLabel: c.isNew ? 'New' : 'Card',
        ),
        title: Text(c.front),
        subtitle: Text(c.back, style: sqlMono),
      ),
    for (final p in r.proposals)
      CheckboxListTile(
        key: ValueKey('proposal-${p.name}'),
        value: !_skipped.contains(p.name),
        onChanged: (on) => setState(
          () => (on ?? false) ? _skipped.remove(p.name) : _skipped.add(p.name),
        ),
        title: Text(p.name),
        subtitle: Text(p.properties.join(', '), style: sqlMono),
      ),
    if (r.proposals.isNotEmpty)
      RunnerBuilder(
        _cards,
        (_) => Padding(
          padding: const EdgeInsets.only(top: AppSpacing.sm),
          child: FilledButton(
            key: const ValueKey('confirm-cards'),
            onPressed:
                _cards.canSend &&
                    r.proposals.any((p) => !_skipped.contains(p.name))
                ? () => _confirm(r.proposals)
                : null,
            child: const Icon(Icons.add_task, semanticLabel: 'Add'),
          ),
        ),
      ),
    for (final f in r.refused)
      ListTile(
        leading: const Icon(Icons.block, semanticLabel: 'Refused'),
        title: Text(f.name),
        subtitle: Text(f.reason),
      ),
    if (r.ankiLine != null) Text(r.ankiLine!),
  ];
}
