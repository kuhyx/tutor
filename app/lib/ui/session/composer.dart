/// The answer composer (`static/questions.js`): a box per question of the
/// latest tutor message, sent as ONE message; else a plain box. Boxes get
/// the question's choices as chips and a "Hint" bulb inside. Drafts
/// survive a reload; Ctrl+Enter sends. Phone: one question at a time (dots,
/// swipe right = back), one row [hint][don't know][field][check / send] at a
/// tighter density, no Ctrl+Enter hint. A question with choices shows them
/// first and keeps the field behind a keyboard glyph; with the keyboard up
/// the chips go and a small box (3 lines, growing to 6) sits under the
/// question, the tutor's last message taking the room above.
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/ui/session/composer_layout.dart';
import 'package:tutor/ui/session/composer_parts.dart';
import 'package:tutor/ui/session/composer_step.dart';

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
    this.keyboard = false,
    super.key,
  });

  /// The phone keyboard is up (false on the desktop).
  final bool keyboard;

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
  var _opened = <int>{}; // phone: choices questions whose field is open
  final _focus = FocusNode();

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
    _focus.dispose();
    super.dispose();
  }

  String _draftKey() => draftKeyFor(widget.sid, widget.latest);

  // Boxes are rebuilt only when the latest tutor message changes, so a
  // poll never wipes what is being typed; a re-keyed message asking the
  // same questions keeps their answers (and the phone's step).
  void _rebuild({bool carry = false}) {
    final (was, typed) = (_asked, [for (final b in _boxes) b.text]);
    _asked = askedIn(widget.latest);
    _key = _draftKey();
    final same = carry && listEquals(textsOf(was), textsOf(_asked));
    _step = same ? _step : 0;
    _moved = same && _moved;
    _opened = same ? _opened : <int>{};
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
    latchOwnWords(_boxes, _asked, _opened);
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
        setState(() {
          _step = 0;
          _opened = <int>{};
        });
      }
    }
  }

  // Phone, a question with choices: the field stays closed until asked for
  // (the keyboard glyph), the keyboard rising, or own words in it.
  bool _fieldOpen(int i) =>
      _asked[i].choices.isEmpty || _opened.contains(i) || widget.keyboard;

  void _openField() {
    setState(() => _opened.add(_step));
    WidgetsBinding.instance.addPostFrameCallback((_) => _focus.requestFocus());
  }

  void _pick(int i, String c) => _boxes[i].value = TextEditingValue(
    text: c,
    selection: TextSelection.collapsed(offset: c.length),
  );

  void _hint() {
    if (widget.enabled) unawaited(widget.onSend('Hint'));
  }

  void _dontKnow() {
    if (widget.enabled) unawaited(widget.onSend(kDontKnow));
  }

  void _go(int step) => setState(() {
    _step = step;
    _moved = true;
  });

  // Keyboard up over question boxes: no chips; the message above gets the
  // room, the field is a small box that grows with the typing.
  bool get _typing => widget.phone && widget.keyboard && _asked.isNotEmpty;

  Widget _box(int i, String label) => AnswerBox(
    controller: _boxes[i],
    label: label,
    focusNode: widget.phone ? _focus : null,
    minLines: widget.phone
        ? (widget.keyboard ? 3 : 1)
        : (_asked.isEmpty ? 3 : 1),
    maxLines: widget.phone ? 6 : 12,
    dense: widget.phone,
    hint: _asked.isNotEmpty,
    onHint: widget.enabled ? _hint : null,
  );

  Widget _chips(int i) => AnswerChips(
    // Typing: the chips make room for the field (the keyboard is up).
    choices: _typing ? const [] : _asked[i].choices,
    selected: _boxes[i].text,
    onPick: (c) => _pick(i, c),
  );

  @override
  Widget build(BuildContext context) {
    final canSend = widget.enabled && _compose().trim().isNotEmpty;
    return ComposerLayout(
      asked: _asked,
      phone: widget.phone,
      canSend: canSend,
      plainLabel: _plainLabel,
      field: _box,
      chips: _chips,
      onSend: () => unawaited(_send()),
      step: () => PhoneStep(
        asked: _asked,
        step: _step,
        typing: _typing,
        fieldOpen: _fieldOpen(_step),
        enabled: widget.enabled,
        canSend: canSend,
        chips: _chips,
        field: (i) => _box(i, 'Your answer'),
        onGo: _go,
        onHint: _hint,
        onDontKnow: _dontKnow,
        onOpenField: _openField,
        onSend: () => unawaited(_send()),
      ),
    );
  }
}
