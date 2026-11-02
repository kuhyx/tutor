import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/mock/mock_links.dart';
import 'package:tutor/mock/mock_queue.dart';
import 'package:tutor/mock/mock_requests.dart';
import 'package:tutor/mock/mock_session.dart';
import 'package:tutor/mock/mock_test_screen.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/sql/done_listener.dart';

const List<int> _lengths = [30, 45, mockMinutes, 90];

/// Pick the length and start; the server assembles the paper.
class MockStartScreen extends StatefulWidget {
  /// Creates the screen.
  const new({required this.services, required this.links, super.key});

  /// Services.
  final TutorServices services;

  /// Where the result's study buttons go.
  final MockLinks links;

  @override
  State<MockStartScreen> createState() => _MockStartScreenState();
}

class _MockStartScreenState extends State<MockStartScreen> {
  late final _start = RequestRunner(
    widget.services.relay,
    stallAfter: sessionStallAfter,
  );
  late final VoidCallback _unlisten;
  int _minutes = mockMinutes;
  String? _problem;

  @override
  void initState() {
    super.initState();
    _unlisten = listenDone(_start, _begin);
  }

  @override
  void dispose() {
    _unlisten();
    unawaited(_start.dispose());
    super.dispose();
  }

  void _begin(Json data) {
    final s = widget.services;
    final MockSession session;
    try {
      session = MockSession.begin(
        s.kv,
        MockAnswerQueue(s.kv),
        relayAnswerSender(s.relay),
        data,
      )..update();
    } on FormatException catch (e) {
      setState(() => _problem = e.message);
      return;
    }
    Navigator.of(context).pushReplacement(
      MaterialPageRoute<void>(
        builder: (_) =>
            MockTestScreen(services: s, session: session, links: widget.links),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Icon(Icons.quiz_outlined, semanticLabel: 'Mock test'),
    ),
    body: PageList(
      children: [
        Wrap(
          spacing: AppSpacing.sm,
          children: [
            for (final m in _lengths)
              ChoiceChip(
                key: ValueKey('minutes-$m'),
                label: Text('$m'),
                selected: _minutes == m,
                onSelected: (_) => setState(() => _minutes = m),
              ),
          ],
        ),
        RunnerBuilder(
          _start,
          (_) => FilledButton(
            key: const ValueKey('start'),
            onPressed: _start.canSend
                ? () => unawaited(_start.run(mockStart(_minutes)))
                : null,
            child: const Icon(Icons.play_arrow, semanticLabel: 'Start'),
          ),
        ),
        RequestStatusLine(_start),
        if (_problem != null) Text(_problem!),
      ],
    ),
  );
}
