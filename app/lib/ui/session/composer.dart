/// The answer composer (`static/questions.js`): one box per question of the
/// latest tutor message plus "Your own comment", sent as ONE message; else
/// a plain answer box. Drafts survive a reload (per session + message) and
/// are dropped once sent. Ctrl+Enter sends.
library;

import 'dart:async';
import 'dart:convert';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/storage/kv_store.dart';

/// The composer.
class Composer extends StatefulWidget {
  /// Creates the composer for session [sid]; [latest] decides boxes.
  const new({
    required this.sid,
    required this.latest,
    required this.kv,
    required this.enabled,
    required this.onSend,
    super.key,
  });

  /// Session id.
  final String sid;

  /// Latest message (boxes when it is the tutor's and asks something).
  final KeyedMessage? latest;

  /// Draft store.
  final KvStore kv;

  /// False while a turn is in flight.
  final bool enabled;

  /// Sends the composed text; true once the worker has it.
  final Future<bool> Function(String text) onSend;

  @override
  State<Composer> createState() => _ComposerState();
}

class _ComposerState extends State<Composer> {
  List<Asked> _asked = const [];
  String _key = '';
  List<TextEditingController> _boxes = [];

  @override
  void initState() {
    super.initState();
    _rebuild();
  }

  @override
  void didUpdateWidget(Composer old) {
    super.didUpdateWidget(old);
    if (_draftKey() != _key) _rebuild();
  }

  @override
  void dispose() {
    for (final b in _boxes) {
      b.dispose();
    }
    super.dispose();
  }

  String _draftKey() {
    final m = widget.latest;
    final asked = m != null && m.message.role == 'tutor'
        ? askedOf(m.message)
        : const <Asked>[];
    return asked.isEmpty
        ? plainDraftKey(widget.sid)
        : answersDraftKey(widget.sid, m!.key);
  }

  // Boxes are rebuilt only when the latest tutor message changes, so a
  // poll never wipes what is being typed.
  void _rebuild() {
    final m = widget.latest;
    _asked = m != null && m.message.role == 'tutor'
        ? askedOf(m.message)
        : const [];
    _key = _draftKey();
    for (final b in _boxes) {
      b.dispose();
    }
    _boxes = [
      for (var i = 0; i < (_asked.isEmpty ? 1 : _asked.length + 1); i++)
        TextEditingController()..addListener(_save),
    ];
    final key = _key;
    unawaited(
      widget.kv.get(key).then((raw) {
        if (!mounted || raw == null || key != _key) return;
        final saved = (jsonDecode(raw) as List).cast<String>();
        for (final (i, v) in saved.indexed) {
          if (i < _boxes.length) _boxes[i].text = v;
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
        setState(() {});
      }
    }
  }

  Widget _box(int i, String label) => Padding(
    padding: const EdgeInsets.only(bottom: AppSpacing.sm),
    child: TextField(
      controller: _boxes[i],
      readOnly: !widget.enabled,
      minLines: _asked.isEmpty ? 3 : 1,
      maxLines: 12,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final canSend = widget.enabled && _compose().trim().isNotEmpty;
    return CallbackShortcuts(
      bindings: {
        const SingleActivator(LogicalKeyboardKey.enter, control: true): () =>
            unawaited(_send()),
      },
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_asked.isEmpty)
            _box(0, 'Your answer. Reason it out; guesses are welcome.')
          else ...[
            for (final (i, a) in _asked.indexed) ...[
              Text('${a.heading}: ${a.text}', style: text.labelLarge),
              const SizedBox(height: AppSpacing.xs),
              _box(i, 'Your answer'),
            ],
            _box(_asked.length, 'Your own comment'),
          ],
          Row(
            children: [
              Expanded(
                child: Text('Ctrl+Enter to send', style: text.bodySmall),
              ),
              FilledButton(
                onPressed: canSend ? _send : null,
                child: const Text('Send'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
