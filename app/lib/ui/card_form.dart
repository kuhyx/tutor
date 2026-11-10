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
import 'package:tutor/ui/fit_layouts.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/icon_field.dart';
import 'package:tutor/widgets/spoken_label.dart';

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

  // A field named by its glyph; [limit] shows the live word count beside
  // it (outside the field: a changing node inside the merged field node
  // trips the framework's semantics asserts).
  Widget _field(
    TextEditingController c,
    IconData icon,
    String label, {
    int lines = 2,
    int? limit,
  }) {
    final field = FieldLabel(
      semanticLabel: label,
      child: TextField(
        controller: c,
        minLines: 1,
        maxLines: lines,
        onChanged: (_) => setState(() {}),
        decoration: iconDecoration(icon),
      ),
    );
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: limit == null
          ? field
          : Row(
              children: [
                Expanded(child: field),
                const SizedBox(width: AppSpacing.sm),
                Text(
                  '${wordCount(c.text)}/$limit',
                  style: TextStyle(
                    color: wordCount(c.text) > limit
                        ? Theme.of(context).colorScheme.error
                        : null,
                  ),
                ),
              ],
            ),
    );
  }

  // The field a local problem is about, by the sentence's first word.
  static IconData _problemIcon(String p) =>
      switch (p.split(RegExp('[: ]')).first) {
        'Front' => Icons.help_outline,
        'Back' => Icons.lightbulb_outline,
        'Source' => Icons.link,
        'Excerpt' => Icons.format_quote,
        _ => Icons.tips_and_updates_outlined,
      };

  @override
  Widget build(BuildContext context) {
    final problems = _problems;
    final fields = [
      _field(
        _front,
        Icons.help_outline,
        'Front (question, <=$kFrontWords words)',
        limit: kFrontWords,
      ),
      _field(
        _back,
        Icons.lightbulb_outline,
        'Back (answer, <=$kBackWords words)',
        lines: 3,
        limit: kBackWords,
      ),
      _field(_source, Icons.link, 'Source (https link)', lines: 1),
      _field(
        _excerpt,
        Icons.format_quote,
        'Excerpt (verbatim from the source)',
        lines: 4,
      ),
      _field(
        _requires,
        Icons.account_tree_outlined,
        'Requires (card ids, comma separated)',
        lines: 1,
      ),
      _field(
        _mnemonic,
        Icons.tips_and_updates_outlined,
        'Mnemonic (optional, one line)',
        lines: 1,
      ),
      if (problems.isNotEmpty)
        Wrap(
          spacing: AppSpacing.sm,
          children: [
            for (final p in problems)
              CueChip(
                kind: CueKind.error,
                icon: _problemIcon(p),
                semanticLabel: p,
              ),
          ],
        ),
    ];
    final status = RequestStatusLine(widget.runner);
    // Phone: Save stays under the fields, above the keyboard.
    final save = Align(
      alignment: Alignment.centerRight,
      child: SpokenLabel(
        semanticLabel: 'Save card',
        button: true,
        enabled: problems.isEmpty,
        onTap: problems.isEmpty ? _save : null,
        child: FilledButton(
          onPressed: problems.isEmpty ? _save : null,
          child: const Icon(Icons.save_outlined),
        ),
      ),
    );
    return Scaffold(
      appBar: AppBar(
        title: SpokenLabel(
          semanticLabel: widget.card == null ? 'New card' : 'Edit card',
          child: Icon(
            widget.card == null ? Icons.note_add_outlined : Icons.edit_outlined,
          ),
        ),
      ),
      body: fitForm(
        context,
        fields: fields,
        bar: [status, save],
        wide: (all) => PageList(children: all),
      ),
    );
  }
}
