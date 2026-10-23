/// Edit or add one card. Local checks first (word limits, https source,
/// excerpt length); Save sends `card_edit`, and the worker fetches the
/// source and verifies the excerpt verbatim (`edit_refused` + reason).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/editor/card_rules.dart';
import 'package:tutor/model/card.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';

/// The card form.
class CardForm extends StatefulWidget {
  /// Creates the form; [card] null = a new card in [module].
  const new({
    required this.runner,
    required this.subject,
    required this.module,
    required this.onSaved,
    this.cardId,
    this.card,
    super.key,
  });

  /// Runs `card_edit`.
  final RequestRunner runner;

  /// Subject id.
  final String subject;

  /// Module id.
  final String module;

  /// Existing card id.
  final String? cardId;

  /// Existing card.
  final StudyCard? card;

  /// Called after a successful save.
  final VoidCallback onSaved;

  @override
  State<CardForm> createState() => _CardFormState();
}

class _CardFormState extends State<CardForm> {
  late final _front = TextEditingController(text: widget.card?.front);
  late final _back = TextEditingController(text: widget.card?.back);
  late final _source = TextEditingController(text: widget.card?.source);
  late final _excerpt = TextEditingController(text: widget.card?.excerpt);
  late final _requires = TextEditingController(
    text: widget.card?.requires.join(', '),
  );
  late final _mnemonic = TextEditingController(text: widget.card?.mnemonic);

  @override
  void dispose() {
    for (final c in [_front, _back, _source, _excerpt, _requires, _mnemonic]) {
      c.dispose();
    }
    super.dispose();
  }

  List<String> get _problems => cardProblems(
    front: _front.text,
    back: _back.text,
    source: _source.text,
    excerpt: _excerpt.text,
    mnemonic: _mnemonic.text,
  );

  Future<void> _save() async {
    if (_problems.isNotEmpty) return;
    final status = await widget.runner.run(
      RequestBody.cardEdit(
        subject: widget.subject,
        card: widget.cardId,
        module: widget.module,
        front: _front.text.trim(),
        back: _back.text.trim(),
        source: _source.text.trim(),
        excerpt: _excerpt.text.trim(),
        requires: [
          for (final r in _requires.text.split(','))
            if (r.trim().isNotEmpty) r.trim(),
        ],
        mnemonic: _mnemonic.text.trim(),
      ),
    );
    if (status is RelayDone && mounted) {
      widget.onSaved();
      Navigator.of(context).pop();
    }
  }

  Widget _field(TextEditingController c, String label, {int lines = 2}) =>
      Padding(
        padding: const EdgeInsets.only(bottom: AppSpacing.md),
        child: TextField(
          controller: c,
          minLines: 1,
          maxLines: lines,
          onChanged: (_) => setState(() {}),
          decoration: InputDecoration(
            labelText: label,
            border: const OutlineInputBorder(),
          ),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final problems = _problems;
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.card == null ? 'New card' : 'Edit card'),
      ),
      body: PageList(
        children: [
          _field(_front, 'Front (question, <=$kFrontWords words)'),
          _field(_back, 'Back (answer, <=$kBackWords words)', lines: 3),
          _field(_source, 'Source (https link)', lines: 1),
          _field(_excerpt, 'Excerpt (verbatim from the source)', lines: 4),
          _field(_requires, 'Requires (card ids, comma separated)', lines: 1),
          _field(_mnemonic, 'Mnemonic (optional, one line)', lines: 1),
          for (final p in problems)
            Text(
              p,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          RequestStatusLine(widget.runner),
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton(
              onPressed: problems.isEmpty ? _save : null,
              child: const Text('Save card'),
            ),
          ),
        ],
      ),
    );
  }
}
