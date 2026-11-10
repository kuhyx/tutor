import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/coach/coach_requests.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/ui/coach/coach_parts.dart';
import 'package:tutor/ui/coach/coach_reveal.dart';
import 'package:tutor/ui/coach/coach_session.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/fit_pages.dart';
import 'package:tutor/ui/layout.dart';
import 'package:tutor/ui/sql/lesson_parts.dart';
import 'package:tutor/ui/sql/problem_cue.dart';
import 'package:tutor/widgets/content_text.dart';

/// The chat tab: thread, pinned snippet, notices, answer box and actions.
/// `onPostMortem` opens the cards view once the session is done; the
/// statement stays above the thread, capped, unless `sidePane` shows it.
class CoachChat extends StatefulWidget {
  /// Creates the pane.
  const new({
    required this.session,
    required this.onPostMortem,
    required this.sidePane,
    super.key,
  });

  /// The session.
  final CoachSession session;

  /// Opens the post-mortem.
  final VoidCallback onPostMortem;

  /// The statement is in a side pane.
  final bool sidePane;

  @override
  State<CoachChat> createState() => _CoachChatState();
}

class _CoachChatState extends State<CoachChat> {
  final _focus = FocusNode();
  final _scroll = ScrollController();
  final _pages = FitPageController();
  int _turns = -1;
  bool _statementOpen = true;

  CoachSession get _s => widget.session;

  @override
  void initState() {
    super.initState();
    _focus.addListener(_toEnd);
    _s.addListener(_toEnd);
  }

  @override
  void dispose() {
    _s.removeListener(_toEnd);
    _focus
      ..removeListener(_toEnd)
      ..dispose();
    _scroll.dispose();
    _pages.dispose();
    super.dispose();
  }

  void _toEnd() {
    // Phone: a new turn shows from its top.
    if (_s.thread.length != _turns) {
      _turns = _s.thread.length;
      _pages.toLast();
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) _scroll.jumpTo(_scroll.position.maxScrollExtent);
    });
  }

  Future<void> _reveal() async {
    if (await askReveal(context)) _s.send(coachReveal);
  }

  void _submit({bool solved = false}) {
    final text = _s.answer.text.trim();
    if (text.isEmpty) return;
    _s.answer.clear();
    if (!solved && text.toLowerCase() == coachReveal) {
      unawaited(_reveal());
    } else {
      _s.send(text, solved: solved);
    }
  }

  void _pick(String choice) {
    if (choice.toLowerCase() == coachReveal) {
      unawaited(_reveal());
    } else {
      _s.send(choice);
    }
  }

  void _prefix(String kind) {
    final text = _s.answer.text;
    if (!text.trimLeft().startsWith('$kind:')) {
      _s.answer.text = '$kind: $text';
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: Listenable.merge([_s, _s.turns.changes]),
    builder: (context, _) {
      final o = _s.opened;
      final pin = _s.pin;
      return Column(
        children: [
          StatusStrip(_s.state),
          if (o != null && o.retest)
            ListTile(
              dense: true,
              leading: const Icon(Icons.event_repeat, semanticLabel: 'Re-test'),
              title: Text(AppLocalizations.of(context).retestNoSubmit),
            ),
          if (o != null && !widget.sidePane)
            _flex(
              FoldingStatement(
                title: o.title,
                md: o.statementMd,
                open: _statementOpen,
                onToggle: () =>
                    setState(() => _statementOpen = !_statementOpen),
              ),
            ),
          const Divider(height: 1),
          Expanded(child: _thread(context)),
          if (_s.turns.busy) const LinearProgressIndicator(),
          RequestStatusLine(_s.turns),
          if (_s.note != null) noteCue(_s.note!, key: const ValueKey('note')),
          if (_s.choices.isNotEmpty)
            ChoiceButtons(choices: _s.choices, onPick: _pick),
          if (pin != null) _flex(PinnedSnippet(md: pin, onClose: _s.unpin)),
          if (_s.state.phase == 'done')
            Padding(
              padding: const EdgeInsets.all(AppSpacing.sm),
              child: FilledButton(
                key: const ValueKey('postmortem'),
                onPressed: widget.onPostMortem,
                child: const Icon(
                  Icons.style_outlined,
                  semanticLabel: 'Post-mortem',
                ),
              ),
            )
          else ...[
            _actions(),
            _box(),
          ],
        ],
      );
    },
  );

  // Phone: capped blocks share what is left with the thread, never
  // overflow it (the keyboard up, a large font).
  Widget _flex(Widget child) =>
      isCompact(context) ? Flexible(child: child) : child;

  Widget _thread(BuildContext context) {
    final items = [
      for (final b in _s.thread) BubbleView(b),
      if (_s.problem != null) problemCue(_s.problem!),
    ];
    const pad = EdgeInsets.all(AppSpacing.md);
    return isCompact(context)
        ? FitPages(controller: _pages, padding: pad, children: items)
        : ListView(controller: _scroll, padding: pad, children: items);
  }

  Widget _box() => AnswerBox(
    controller: _s.answer,
    focus: _focus,
    canSend: _s.canSend,
    onSend: _submit,
  );

  Widget _actions() {
    final gate = _s.state.gate;
    return Row(
      children: [
        if (!gate.open)
          TextButton(
            key: const ValueKey('prefix'),
            onPressed: () => _prefix(gate.kind),
            // The phrase kuhy types as the answer's prefix: content.
            child: ContentText('${gate.kind}:'),
          ),
        IconButton(
          key: const ValueKey('hint'),
          onPressed: _s.canSend ? () => _s.send(coachHint) : null,
          icon: const Icon(Icons.lightbulb_outline, semanticLabel: 'Hint'),
        ),
        ListenableBuilder(
          listenable: _s.answer,
          builder: (context, _) => IconButton(
            key: const ValueKey('solved'),
            onPressed: _s.canSend && _s.answer.text.trim().isNotEmpty
                ? () => _submit(solved: true)
                : null,
            icon: const Icon(Icons.task_alt, semanticLabel: 'Solved'),
          ),
        ),
        IconButton(
          key: const ValueKey('reveal'),
          onPressed: _s.canSend ? () => unawaited(_reveal()) : null,
          icon: const Icon(Icons.visibility_outlined, semanticLabel: 'Reveal'),
        ),
      ],
    );
  }
}
