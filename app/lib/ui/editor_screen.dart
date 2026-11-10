/// Editor (curriculum §8): subject -> module -> cards; edit or add a card
/// (`card_edit`, validated by the worker against its source), flag one
/// (a `flag` event, offline OK), Restore a removed or split card
/// (`card_restore`), Remove one the tutor added (`card_remove`).
library;

import 'dart:async';
import 'dart:developer';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/editor/card_rules.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/model/card.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/progress/terms.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/card_form.dart';
import 'package:tutor/ui/card_state.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/editor_module.dart';
import 'package:tutor/ui/flag_dialog.dart';
import 'package:tutor/ui/layout.dart';
import 'package:tutor/ui/learn_bits.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/spoken_label.dart';

part 'editor_parts.dart';

/// The card editor.
class EditorScreen extends StatefulWidget {
  /// Creates the editor, optionally opened on [subject].
  const new({required this.services, this.subject, super.key});

  /// Services.
  final TutorServices services;

  /// Subject to open first.
  final String? subject;

  @override
  State<EditorScreen> createState() => _EditorScreenState();
}

class _EditorScreenState extends State<EditorScreen> {
  late final RequestRunner _runner = RequestRunner(widget.services.relay);
  late final StreamSubscription<int> _changes;
  Map<String, SubjectData> _subjects = const {};
  FoldResult? _fold;
  String? _subject;
  final _open = <String>{};

  @override
  void initState() {
    super.initState();
    _subject = widget.subject;
    unawaited(_load());
    // Cards land while a module generates: refetch the open subject in
    // place (the list stays on screen; an open card form is its own page).
    _changes = widget.services.rev.catalogChanges.listen(
      (_) => unawaited(_load(fresh: true)),
    );
  }

  @override
  void dispose() {
    unawaited(_changes.cancel());
    unawaited(_runner.dispose());
    super.dispose();
  }

  Future<void> _load({bool fresh = false}) async {
    final s = _subject;
    if (fresh && s != null) {
      try {
        await widget.services.catalog.fetch(s);
      } on Object catch (error) {
        // `on Object`: a background refresh must not throw; the cached
        // subject stays on screen until the next change or save.
        log('editor refresh failed', level: 900, error: error);
      }
    }
    final all = await widget.services.catalog.cached();
    final folded = await foldAll(
      widget.services.events,
      widget.services.catalog,
    );
    if (!mounted) return;
    setState(() {
      _subjects = all;
      _fold = folded;
      _subject ??= all.keys.firstOrNull;
    });
  }

  Future<void> _edit(
    SubjectData s,
    Module m, [
    MapEntry<String, StudyCard>? c,
  ]) => Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => CardForm(
        runner: _runner,
        subject: s.id,
        module: m.id,
        cardId: c?.key,
        card: c?.value,
        onSaved: () => unawaited(_load(fresh: true)),
      ),
    ),
  );

  Future<void> _flag(SubjectData s, String id, StudyCard card) async {
    final reason = await askFlagReason(context);
    if (reason == null) return;
    await widget.services.events.record(
      FlagEvent(
        subject: s.id,
        card: id,
        at: DateTime.now().millisecondsSinceEpoch,
        rev: card.rev,
        reason: reason,
      ),
    );
    if (mounted) {
      showCueSnack(
        context,
        CueKind.ok,
        'Flagged; it leaves review until edited.',
      );
    }
  }

  Future<void> _undo(RequestBody body) async {
    final status = await _runner.run(body);
    if (status is RelayDone) unawaited(_load(fresh: true));
  }

  @override
  Widget build(BuildContext context) {
    final s = _subjects[_subject];
    final fold = _fold;
    final progress = s == null || fold == null
        ? null
        : subjectProgress(s, fold, DateTime.now());
    final compact = isCompact(context);
    return Scaffold(
      appBar: AppBar(
        title: const SpokenLabel(
          semanticLabel: 'Edit cards',
          child: Icon(Icons.edit_note),
        ),
      ),
      body: PageList(
        children: [
          if (_subjects.isNotEmpty)
            DropdownButton<String>(
              value: _subject,
              isExpanded: true,
              items: [
                for (final e in _subjects.entries)
                  DropdownMenuItem(
                    value: e.key,
                    child: ContentText(e.value.meta.title),
                  ),
              ],
              onChanged: (v) => setState(() => _subject = v),
            ),
          RequestStatusLine(_runner),
          if (progress != null && progress.total.cards > 0)
            ProgressSummary(progress.total),
          if (s == null)
            const SizedBox(
              height: 240,
              child: GlyphEmpty(
                icon: Icons.style,
                semanticLabel:
                    'No cards yet. Cards appear once a plan is approved.',
              ),
            )
          else
            for (final m in s.plan?.modules ?? const <Module>[])
              ...moduleRows(
                compact: compact,
                open: _open.contains(m.id),
                onToggle: () =>
                    setState(() => _open.remove(m.id) || _open.add(m.id)),
                title: ContentText(m.title),
                subtitle: _moduleSub(s, m, progress),
                addCard: _addCard(s, m),
                cards: [
                  for (final c in s.cardsOf(m.id))
                    ListTile(
                      leading: CardStateIcon(progress?.cards[c.key]),
                      title: ContentText(c.value.front),
                      subtitle: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          ContentText(c.value.back),
                          Wrap(
                            spacing: AppSpacing.sm,
                            children: [
                              ContentText(hostOf(c.value.source)),
                              CardMarks(c.value, progress?.cards[c.key]),
                            ],
                          ),
                        ],
                      ),
                      isThreeLine: true,
                      onTap: () => _edit(s, m, c),
                      trailing: _actions(s, c),
                    ),
                ],
              ),
        ],
      ),
    );
  }
}

String _cards(int n) => '$n card${n == 1 ? '' : 's'}';
