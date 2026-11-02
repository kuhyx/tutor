import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/coach/coach_requests.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/ui/coach/coach_parts.dart';
import 'package:tutor/ui/coach/coach_reveal.dart';
import 'package:tutor/ui/coach/coach_session.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/sql/lesson_parts.dart';

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
    super.dispose();
  }

  void _toEnd() => WidgetsBinding.instance.addPostFrameCallback((_) {
    if (_scroll.hasClients) _scroll.jumpTo(_scroll.position.maxScrollExtent);
  });

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
            FoldingStatement(
              title: o.title,
              md: o.statementMd,
              open: _statementOpen,
              onToggle: () => setState(() => _statementOpen = !_statementOpen),
            ),
          const Divider(height: 1),
          Expanded(
            child: ListView(
              controller: _scroll,
              padding: const EdgeInsets.all(AppSpacing.md),
              children: [
                for (final b in _s.thread) BubbleView(b),
                if (_s.problem != null) Text(_s.problem!),
              ],
            ),
          ),
          if (_s.turns.busy) const LinearProgressIndicator(),
          RequestStatusLine(_s.turns),
          if (_s.note != null)
            ListTile(
              key: const ValueKey('note'),
              dense: true,
              leading: const Icon(Icons.info_outline, semanticLabel: 'Note'),
              title: Text(_s.note!),
            ),
          if (_s.choices.isNotEmpty)
            ChoiceButtons(choices: _s.choices, onPick: _pick),
          if (pin != null) PinnedSnippet(md: pin, onClose: _s.unpin),
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
            child: Text('${gate.kind}:'),
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
