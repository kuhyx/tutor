/// Drill mode of the Review screen: the model-free fallback for when Claude
/// is out. The front, then 2-4 big option buttons (no typing); a pick is
/// marked right or wrong, the back, excerpt and source show, and a Next
/// pinned under the page asks for another. Keys: 1-4 pick, Space/Enter next. On Android a button
/// syncs AnkiDroid and reports the minutes it credited.
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/drill/anki_sync.dart';
import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/drill/drill_session.dart';
import 'package:tutor/editor/card_rules.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/drill_parts.dart';

/// The drill body.
class DrillView extends StatefulWidget {
  /// Creates the view; [unavailable] seeds the banner, [anki] is injectable.
  const new({required this.services, this.unavailable, this.anki, super.key});

  /// Services.
  final TutorServices services;

  /// Claude-out banner to show from the start (the auto-switch).
  final Unavailable? unavailable;

  /// The AnkiDroid sync; default: the Android intent route.
  final AnkiSync? anki;

  @override
  State<DrillView> createState() => _DrillViewState();
}

class _DrillViewState extends State<DrillView> {
  late final DrillSession _run = DrillSession(
    runner: RequestRunner(widget.services.relay),
    unavailable: widget.unavailable,
  );
  late final AnkiSync _anki =
      widget.anki ??
      AnkiSync(relay: widget.services.relay, launcher: ChannelAnkiLauncher());

  @override
  void initState() {
    super.initState();
    unawaited(_run.next());
  }

  @override
  void dispose() {
    _run.dispose();
    // An injected sync outlives this view (the screen may reopen Drill).
    if (widget.anki == null) _anki.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => CallbackShortcuts(
    bindings: {
      for (final (i, key) in _digits.indexed)
        SingleActivator(key): () => unawaited(_run.pick(i)),
      const SingleActivator(LogicalKeyboardKey.space): _next,
      const SingleActivator(LogicalKeyboardKey.enter): _next,
    },
    child: Focus(
      autofocus: true,
      child: ListenableBuilder(
        listenable: Listenable.merge([_run, _anki]),
        builder: (context, _) => Column(
          children: [
            Expanded(child: PageList(children: _children(context))),
            if (_run.answer != null) _nextBar(),
          ],
        ),
      ),
    ),
  );

  void _next() {
    if (_run.stage == DrillStage.answered) unawaited(_run.next());
  }

  List<Widget> _children(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final q = _run.question;
    final gone = _run.unavailable ?? _anki.unavailable;
    final today = _run.today;
    return [
      if (gone != null) DrillBanner(gone.banner),
      _header(text, today),
      const SizedBox(height: AppSpacing.sm),
      switch (_run.stage) {
        DrillStage.empty => const EmptyState(
          icon: Icons.check_circle_outline,
          title: 'Nothing to drill',
          message: 'No card has enough neighbours to ask about right now.',
        ),
        DrillStage.failed => DrillFailed(_run.error ?? '', _run.retry),
        _ when q == null => const Center(
          child: Padding(
            padding: EdgeInsets.all(AppSpacing.xl),
            child: CircularProgressIndicator(),
          ),
        ),
        _ => _question(context, q),
      },
    ];
  }

  Widget _question(BuildContext context, DrillQuestion q) {
    final text = Theme.of(context).textTheme;
    final a = _run.answer;
    final busy = _run.stage == DrillStage.loading;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Text(q.card.front, style: text.titleLarge),
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        for (var i = 0; i < q.options.length; i++) ...[
          DrillOption(
            q.options[i],
            mark: _mark(i, a),
            onTap: a == null && !busy ? () => unawaited(_run.pick(i)) : null,
          ),
          const SizedBox(height: AppSpacing.sm),
        ],
        if (a != null) ..._graded(text, a),
      ],
    );
  }

  // True on the right option, false on a wrong pick, else null.
  bool? _mark(int i, DrillAnswer? a) {
    if (a == null) return null;
    if (i == a.answerIndex) return true;
    return i == _run.picked ? false : null;
  }

  List<Widget> _graded(TextTheme text, DrillAnswer a) => [
    Text(
      a.correct
          ? 'Correct${a.minuteCredited ? ' · +1 min credited' : ''}'
          : 'Not quite',
      style: text.titleMedium,
    ),
    const SizedBox(height: AppSpacing.xs),
    Text(a.back, style: text.bodyLarge),
    const SizedBox(height: AppSpacing.sm),
    Text(
      '"${a.excerpt}"',
      style: text.bodyMedium?.copyWith(fontStyle: FontStyle.italic),
    ),
    const SizedBox(height: AppSpacing.xs),
    LinkText(hostOf(a.source), a.source),
  ];

  // Pinned under the scrolling page: a long excerpt pushed an inline Next
  // below the fold on a phone (kuhy, 2026-10-15).
  Widget _nextBar() => SafeArea(
    top: false,
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: kPageMaxWidth),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.md,
          AppSpacing.xs,
          AppSpacing.md,
          AppSpacing.md,
        ),
        child: SizedBox(
          width: double.infinity,
          child: FilledButton(
            style: drillButton,
            onPressed: _run.stage == DrillStage.loading ? null : _next,
            child: const Text('Next (Space)'),
          ),
        ),
      ),
    ),
  );

  // One line: the day's credited minutes; on Android the Anki sync beside it.
  Widget _header(TextTheme text, DrillToday? today) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(
        children: [
          Expanded(
            child: Text(
              today == null ? '' : 'Today: ${today.creditedMin} min credited',
              style: text.bodySmall,
            ),
          ),
          if (_anki.launcher.supported)
            TextButton.icon(
              onPressed: _anki.running ? null : () => unawaited(_anki.run()),
              icon: const Icon(Icons.sync),
              label: const Text('Sync Anki & credit'),
            ),
        ],
      ),
      if (_anki.message != null) Text(_anki.message!, style: text.bodySmall),
    ],
  );
}

const List<LogicalKeyboardKey> _digits = [
  LogicalKeyboardKey.digit1,
  LogicalKeyboardKey.digit2,
  LogicalKeyboardKey.digit3,
  LogicalKeyboardKey.digit4,
];
