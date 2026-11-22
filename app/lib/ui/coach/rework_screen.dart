/// `/rework/<subject>/<module>/<slug>`, the LeetCode lock's `?` on a
/// problem: kuhy says what was unclear, the tutor replies and adds cards to
/// the module (tutor/relay/rework.py). Glyphs only; the chat is content.
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/coach/rework_requests.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/sql/lesson_models.dart';
import 'package:tutor/ui/request_status.dart';
import 'package:tutor/ui/sql/done_listener.dart';
import 'package:tutor/ui/sql/lesson_parts.dart';
import 'package:tutor/ui/sql/problem_cue.dart';
import 'package:tutor/widgets/content_text.dart';

/// Opens the rework chat on [slug] for [module] of [subject].
Future<void> openRework(
  BuildContext context,
  TutorServices s,
  String subject,
  String module,
  String slug,
) => Navigator.of(context).push(
  MaterialPageRoute<void>(
    builder: (_) =>
        ReworkScreen(services: s, subject: subject, module: module, slug: slug),
  ),
);

/// The rework chat: thread, the cards it added, the answer box.
class ReworkScreen extends StatefulWidget {
  /// Creates the screen and opens the chat.
  const new({
    required this.services,
    required this.subject,
    required this.module,
    required this.slug,
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// The tutor subject id the guard named.
  final String subject;

  /// That subject's module id.
  final String module;

  /// The LeetCode titleSlug.
  final String slug;

  @override
  State<ReworkScreen> createState() => _ReworkState();
}

class _ReworkState extends State<ReworkScreen> {
  late final _open = RequestRunner(widget.services.relay);
  late final _turns = RequestRunner(
    widget.services.relay,
    stallAfter: sessionStallAfter,
  );
  late final List<VoidCallback> _stops;
  final _answer = TextEditingController();
  final _focus = FocusNode();
  final List<Bubble> _thread = [];
  final List<ReworkCard> _cards = [];
  ReworkOpened? _opened;
  String? _problem;

  @override
  void initState() {
    super.initState();
    _stops = [listenDone(_open, _onOpened), listenDone(_turns, _onTurn)];
    unawaited(
      _open.run(reworkOpen(widget.subject, widget.module, widget.slug)),
    );
  }

  @override
  void dispose() {
    for (final stop in _stops) {
      stop();
    }
    _answer.dispose();
    _focus.dispose();
    unawaited(_open.dispose());
    unawaited(_turns.dispose());
    super.dispose();
  }

  void _guard(void Function() read) {
    try {
      _problem = null;
      read();
    } on FormatException catch (e) {
      _problem = e.message;
    }
    setState(() {});
  }

  void _onOpened(Map<String, dynamic> data) => _guard(() {
    final o = parseReworkOpened(data);
    _opened = o;
    _thread
      ..clear()
      ..addAll(o.thread);
    _cards
      ..clear()
      ..addAll(o.cards);
  });

  void _onTurn(Map<String, dynamic> data) => _guard(() {
    final t = parseReworkTurn(data);
    if (t.replyMd.isNotEmpty) {
      _thread.add((mine: false, md: t.replyMd, grid: null));
    }
    _cards.addAll(t.cards);
  });

  // The box sends only once opened, and only a non-blank answer.
  void _send() {
    final id = _opened!.reworkId;
    final text = _answer.text.trim();
    setState(() => _thread.add((mine: true, md: text, grid: null)));
    _answer.clear();
    unawaited(_turns.run(reworkTurn(id, text)));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Row(
        children: [
          const Icon(Icons.help_outline, semanticLabel: 'Rework'),
          const SizedBox(width: AppSpacing.sm),
          Flexible(child: ContentText(_opened?.moduleTitle ?? widget.slug)),
        ],
      ),
      actions: [
        Padding(
          padding: const EdgeInsets.only(right: AppSpacing.md),
          child: Badge.count(
            key: const ValueKey('rework-cards'),
            count: _cards.length,
            isLabelVisible: _cards.isNotEmpty,
            child: const Icon(Icons.style_outlined, semanticLabel: 'Cards'),
          ),
        ),
      ],
    ),
    body: Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              for (final b in _thread) BubbleView(b),
              for (final c in _cards)
                ListTile(
                  leading: const Icon(Icons.fiber_new_outlined),
                  title: ContentText(c.front),
                  subtitle: ContentText(c.back),
                ),
              if (_problem != null) problemCue(_problem!),
            ],
          ),
        ),
        RequestStatusLine(_open),
        RequestStatusLine(_turns),
        RunnerBuilder(
          _turns,
          (_) => _turns.busy
              ? const LinearProgressIndicator()
              : const SizedBox.shrink(),
        ),
        RunnerBuilder(
          _turns,
          (_) => AnswerBox(
            controller: _answer,
            focus: _focus,
            canSend: _opened != null && _turns.canSend,
            onSend: _send,
          ),
        ),
      ],
    ),
  );
}
