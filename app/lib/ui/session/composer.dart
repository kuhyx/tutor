/// The answer composer (`static/questions.js`): a box per question of the
/// latest tutor message, sent as ONE message; else a plain box. Boxes get
/// the question's choices as chips plus "Hint" (sends "Hint"). Drafts
/// survive a reload; Ctrl+Enter sends. Phone: one question at a time (dots,
/// swipe right = back), one row [hint][field][check / send] at a tighter
/// density, no Ctrl+Enter hint.
library;

import 'dart:async';
import 'dart:convert';

import 'package:design_system/design_system.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/ui/fit_pages.dart';
import 'package:tutor/ui/session/composer_parts.dart';

/// The composer.
class Composer extends StatefulWidget {
  /// Creates the composer for session [sid]; [latest] decides boxes.
  const new({
    required this.sid,
    required this.latest,
    required this.kv,
    required this.enabled,
    required this.onSend,
    this.phone = false,
    super.key,
  });

  /// Session id.
  final String sid;

  /// Latest message (boxes when it is the tutor's and asks something).
  final KeyedMessage? latest;

  /// Draft store.
  final KvStore kv;

  /// False while a turn is in flight: Send, Ctrl+Enter and Hint wait; the
  /// boxes (and the choices that fill them) stay usable.
  final bool enabled;

  /// Sends the composed text; true once the worker has it.
  final Future<bool> Function(String text) onSend;

  /// The Android app.
  final bool phone;

  @override
  State<Composer> createState() => _ComposerState();
}

/// The plain box's spoken label.
const _plainLabel = 'Your answer. Reason it out; guesses are welcome.';

class _ComposerState extends State<Composer> {
  List<Asked> _asked = const [];
  String _key = '';
  List<TextEditingController> _boxes = [];
  int _step = 0; // phone: the question on screen
  bool _moved = false; // stepped by hand: a late draft keeps it
  @override
  void initState() {
    super.initState();
    _rebuild();
  }

  @override
  void didUpdateWidget(Composer old) {
    super.didUpdateWidget(old);
    if (_draftKey() != _key) _rebuild(carry: old.sid == widget.sid);
  }

  @override
  void dispose() {
    for (final b in _boxes) {
      b.dispose();
    }
    super.dispose();
  }

  List<Asked> _askedNow() {
    final m = widget.latest;
    return m != null && m.message.role == 'tutor'
        ? askedOf(m.message)
        : const [];
  }

  String _draftKey() => _askedNow().isEmpty
      ? plainDraftKey(widget.sid)
      : answersDraftKey(widget.sid, widget.latest!.key);

  // Boxes are rebuilt only when the latest tutor message changes, so a
  // poll never wipes what is being typed; a re-keyed message asking the
  // same questions keeps their answers (and the phone's step).
  void _rebuild({bool carry = false}) {
    final (was, typed) = (_asked, [for (final b in _boxes) b.text]);
    _asked = _askedNow();
    _key = _draftKey();
    final same = carry && listEquals(textsOf(was), textsOf(_asked));
    _step = same ? _step : 0;
    _moved = same && _moved;
    for (final b in _boxes) {
      b.dispose();
    }
    _boxes = [
      for (final v in carriedAnswers(carry ? was : const [], typed, _asked))
        TextEditingController(text: v)..addListener(_save),
    ];
    final key = _key;
    unawaited(
      widget.kv.get(key).then((raw) {
        if (!mounted || raw == null || key != _key) return;
        // Typed before the draft arrived: that typing wins, box by box.
        final typed = _boxes.any((b) => b.text.isNotEmpty);
        fillEmptyBoxes(_boxes, (jsonDecode(raw) as List).cast<String>());
        // Back to where the learner left off: the first unanswered question.
        if (!_moved && !typed && _asked.isNotEmpty) {
          setState(() => _step = resumeStep(_boxes, _asked.length));
        }
      }),
    );
  }

  void _save() {
    setState(() {}); // Send enables with the first typed character.
    final values = [for (final b in _boxes) b.text];
    unawaited(widget.kv.set(_key, jsonEncode(values)));
  }

  String _compose() => _asked.isEmpty
      ? _boxes.single.text.trimRight()
      : composeAnswers(_asked, [for (final b in _boxes) b.text]);

  Future<void> _send() async {
    final text = _compose();
    if (!widget.enabled || text.trim().isEmpty) return;
    final key = _key;
    if (await widget.onSend(text)) {
      await widget.kv.remove(key);
      if (mounted && key == _key) {
        for (final b in _boxes) {
          b
            ..removeListener(_save)
            ..clear()
            ..addListener(_save);
        }
        setState(() => _step = 0);
      }
    }
  }

  void _pick(int i, String c) => _boxes[i].value = TextEditingValue(
    text: c,
    selection: TextSelection.collapsed(offset: c.length),
  );

  void _hint() {
    if (widget.enabled) unawaited(widget.onSend('Hint'));
  }

  void _go(int step) => setState(() {
    _step = step;
    _moved = true;
  });

  Widget _box(int i, String label) => AnswerBox(
    controller: _boxes[i],
    label: label,
    minLines: _asked.isEmpty && !widget.phone ? 3 : 1,
    maxLines: widget.phone ? 6 : 12,
    dense: widget.phone,
  );

  Widget _chips(int i) => AnswerChips(
    choices: _asked[i].choices,
    enabled: widget.enabled,
    onPick: (c) => _pick(i, c),
    onHint: _hint,
    hint: !widget.phone,
  );

  Offset _swipe = Offset.zero; // phone: the drag on the question so far

  // One question at a time: dots, its text and chips, then one row
  // [hint][box][check], the check turning into Send on the last question.
  List<Widget> _phoneStep(bool canSend) {
    final a = _asked[_step];
    final last = _step == _asked.length - 1;
    return [
      if (_asked.length > 1) StepDots(step: _step, total: _asked.length),
      // Pages, never a scroll (build-mobile-app R7): a long question pages.
      Flexible(
        // Swipe right on the question: the previous one. Raw pointers, so
        // the question's SelectionArea cannot win the drag in the arena.
        child: Listener(
          onPointerDown: (e) => _swipe = Offset.zero,
          onPointerMove: (e) => _swipe += e.delta,
          onPointerUp: (_) {
            final d = _swipe;
            if (d.dx > kPhoneTarget && d.dx > 2 * d.dy.abs() && _step > 0) {
              _go(_step - 1);
            }
          },
          child: FitPages(
            key: ValueKey('step-$_step'),
            children: [
              QuestionLabel(a, fontSize: kPhoneText),
              const SizedBox(height: AppSpacing.sm),
              _chips(_step),
            ],
          ),
        ),
      ),
      PhoneRow(
        hint: phoneGlyph(
          Icons.lightbulb_outline,
          'Hint',
          widget.enabled ? _hint : null,
        ),
        field: _box(_step, 'Your answer'),
        action: last
            ? phoneGlyph(
                Icons.send,
                'Send',
                canSend ? _send : null,
                filled: true,
              )
            : phoneGlyph(
                Icons.check,
                'Next',
                () => _go(_step + 1),
                filled: true,
              ),
      ),
    ];
  }

  List<Widget> _deskBoxes(TextTheme text, bool canSend) => [
    for (final (i, a) in _asked.indexed) ...[
      QuestionLabel(a),
      const SizedBox(height: AppSpacing.xs),
      _chips(i),
      _box(i, 'Your answer'),
    ],
    SendRow(canSend: canSend, onSend: _send, hint: 'Ctrl+Enter to send'),
  ];

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final canSend = widget.enabled && _compose().trim().isNotEmpty;
    final body = CallbackShortcuts(
      bindings: {
        const SingleActivator(LogicalKeyboardKey.enter, control: true): () =>
            unawaited(_send()),
      },
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_asked.isEmpty && widget.phone)
            PhoneRow(
              field: _box(0, _plainLabel),
              action: phoneGlyph(
                Icons.send,
                'Send',
                canSend ? _send : null,
                filled: true,
              ),
            )
          else if (_asked.isEmpty) ...[
            _box(0, _plainLabel),
            SendRow(
              canSend: canSend,
              onSend: _send,
              hint: 'Ctrl+Enter to send',
            ),
          ] else if (widget.phone)
            ..._phoneStep(canSend)
          else
            ..._deskBoxes(text, canSend),
        ],
      ),
    );
    // Phone: the scrolling step view takes the panel's height (flex child).
    return widget.phone ? Flexible(child: body) : body;
  }
}
