/// Review (curriculum §5): offline FSRS queue across all subjects (or one
/// subject's, from a Review inside that subject). Front ->
/// reveal back + excerpt + source link -> Again/Hard/Good/Easy, or Flag.
/// Keys: Space reveals, 1-4 rate, F flags. The app bar switches to Drill
/// (`drill_view.dart`): pick-an-answer cards from the PC, no model.
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/drill/anki_sync.dart';
import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/editor/card_rules.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/review/review_session.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/drill_view.dart';
import 'package:tutor/ui/flag_dialog.dart';
import 'package:tutor/ui/review_end.dart';

/// The Review screen.
class ReviewScreen extends StatefulWidget {
  /// Creates the screen; [now] is injectable for tests.
  const new({
    required this.services,
    this.drill = false,
    this.unavailable,
    this.anki,
    this.module,
    this.subject,
    this.subjectTitle,
    this.now,
    super.key,
  });

  /// Only this subject's due cards (null: every subject's).
  final String? subject;

  /// Its title, for the app bar.
  final String? subjectTitle;

  /// Services.
  final TutorServices services;

  /// Reviews this module (every taught card, Again/Hard requeued) instead
  /// of the due queue.
  final ModuleRef? module;

  /// Opens in Drill mode.
  final bool drill;

  /// The "Claude limit" banner for Drill (the auto-switch).
  final Unavailable? unavailable;

  /// Drill's AnkiDroid sync (tests inject; default: the Android intent).
  final AnkiSync? anki;

  /// Clock.
  final DateTime Function()? now;

  @override
  State<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends State<ReviewScreen> {
  late final Future<ReviewSession> _run = _start();
  final _focus = FocusNode();
  late bool _drill = widget.drill;

  Future<ReviewSession> _start() async {
    final now = widget.now ?? DateTime.now;
    final s = widget.services;
    final module = widget.module;
    final items = module == null
        ? await dueItems(
            catalog: s.catalog,
            events: s.events,
            now: now().toUtc(),
            subject: widget.subject,
          )
        : await moduleItems(
            catalog: s.catalog,
            events: s.events,
            module: module,
          );
    return ReviewSession(
      items: items,
      events: s.events,
      requeue: module != null,
      now: now,
    );
  }

  @override
  void dispose() {
    _focus.dispose();
    unawaited(_run.then((r) => r.dispose()));
    super.dispose();
  }

  Future<void> _flag(ReviewSession run) async {
    final reason = await askFlagReason(context);
    if (reason != null) await run.flag(reason);
    _focus.requestFocus();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        _drill
            ? 'Drill'
            : widget.module != null
            ? 'Review: ${widget.module!.title}'
            : widget.subject != null
            ? 'Review: ${widget.subjectTitle ?? 'this subject'}'
            : 'Review',
      ),
      actions: [
        TextButton(
          onPressed: () => setState(() => _drill = !_drill),
          child: Text(_drill ? 'Review' : 'Drill'),
        ),
      ],
    ),
    body: _drill
        ? DrillView(
            services: widget.services,
            unavailable: widget.unavailable,
            anki: widget.anki,
          )
        : _review(),
  );

  Widget _review() => FutureBuilder<ReviewSession>(
    future: _run,
    builder: (context, snap) {
      if (snap.connectionState != ConnectionState.done) {
        return const Center(child: CircularProgressIndicator());
      }
      if (snap.hasError) {
        return PageList(children: [Text('Could not load: ${snap.error}')]);
      }
      final run = snap.requireData;
      return ListenableBuilder(
        listenable: run,
        builder: (context, _) => CallbackShortcuts(
          bindings: {
            const SingleActivator(LogicalKeyboardKey.space): run.reveal,
            for (final g in Grade.values)
              SingleActivator(_digit(g.value)): () => unawaited(run.rate(g)),
            const SingleActivator(LogicalKeyboardKey.keyF): () =>
                unawaited(_flag(run)),
          },
          child: Focus(
            focusNode: _focus,
            autofocus: true,
            child: _body(context, run),
          ),
        ),
      );
    },
  );

  static LogicalKeyboardKey _digit(int n) => switch (n) {
    1 => LogicalKeyboardKey.digit1,
    2 => LogicalKeyboardKey.digit2,
    3 => LogicalKeyboardKey.digit3,
    _ => LogicalKeyboardKey.digit4,
  };

  Widget _body(BuildContext context, ReviewSession run) {
    final item = run.current;
    final text = Theme.of(context).textTheme;
    if (item == null) return ReviewEnd(run, module: widget.module != null);
    final card = item.card;
    return PageList(
      children: [
        Text('${item.subjectTitle} · ${run.left} left', style: text.bodySmall),
        const SizedBox(height: AppSpacing.md),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(card.front, style: text.titleLarge),
                if (run.revealed) ...[
                  const Divider(height: AppSpacing.xl),
                  Text(card.back, style: text.bodyLarge),
                  const SizedBox(height: AppSpacing.md),
                  Text(
                    '"${card.excerpt}"',
                    style: text.bodyMedium?.copyWith(
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  LinkText(hostOf(card.source), card.source),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        if (!run.revealed)
          FilledButton(
            onPressed: run.reveal,
            child: const Text('Show answer (Space)'),
          )
        else
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            alignment: WrapAlignment.center,
            children: [
              for (final g in Grade.values)
                (g == Grade.good ? FilledButton.new : OutlinedButton.new)(
                  onPressed: () => run.rate(g),
                  child: Text('${g.value} ${_label(g)}'),
                ),
            ],
          ),
        const SizedBox(height: AppSpacing.sm),
        Align(
          child: TextButton.icon(
            onPressed: () => _flag(run),
            icon: const Icon(Icons.flag_outlined),
            label: const Text('Flag (F)'),
          ),
        ),
      ],
    );
  }

  static String _label(Grade g) => switch (g) {
    Grade.again => 'Again',
    Grade.hard => 'Hard',
    Grade.good => 'Good',
    Grade.easy => 'Easy',
  };
}
