/// History (curriculum §8): past sessions newest first; archived and
/// auto-archived ones behind a toggle; tap opens the transcript.
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/history/history.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// The History screen.
class HistoryScreen extends StatefulWidget {
  /// Creates the screen.
  const new({required this.services, super.key});

  /// Services.
  final TutorServices services;

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  late Future<HistoryLists> _lists = _load();
  bool _showArchived = false;

  Future<HistoryLists> _load() async =>
      splitHistory(await widget.services.history.load());

  void _reload() => setState(() {
    _lists = _load()..ignore(); // FutureBuilder reports errors
  });

  Future<void> _open(String sid) async {
    await openTranscript(context, widget.services, sid);
    if (mounted) _reload();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      actions: [
        GlyphButton(
          icon: Icons.refresh,
          semanticLabel: 'Reload',
          onPressed: _reload,
        ),
      ],
    ),
    body: FutureBuilder<HistoryLists>(
      future: _lists,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          return PageList(
            children: [
              CueChip(
                kind: CueKind.error,
                semanticLabel: 'Could not load: ${snap.error}',
              ),
            ],
          );
        }
        final lists = snap.requireData;
        return PageList(
          children: [
            if (lists.shown.isEmpty) const _Empty(),
            for (final e in lists.shown)
              _Row(entry: e, onTap: () => unawaited(_open(e.sid))),
            if (lists.hidden.isNotEmpty)
              Align(
                alignment: Alignment.centerLeft,
                child: GlyphButton(
                  icon: _showArchived
                      ? Icons.visibility_off_outlined
                      : Icons.inventory_2_outlined,
                  semanticLabel:
                      '${_showArchived ? 'Hide' : 'Show'} archived '
                      '(${lists.hidden.length})',
                  count: lists.hidden.length,
                  selected: _showArchived,
                  onPressed: () =>
                      setState(() => _showArchived = !_showArchived),
                ),
              ),
            if (_showArchived)
              for (final e in lists.hidden)
                _Row(entry: e, onTap: () => unawaited(_open(e.sid))),
          ],
        );
      },
    ),
  );
}

/// No past sessions: a big outline glyph.
class _Empty extends StatelessWidget {
  const new();

  @override
  Widget build(BuildContext context) => const Padding(
    padding: EdgeInsets.all(AppSpacing.xl),
    child: SpokenLabel(
      semanticLabel: 'No past sessions',
      child: Icon(Icons.history, size: 64),
    ),
  );
}

class _Row extends StatelessWidget {
  const new({required this.entry, required this.onTap});

  final HistoryEntry entry;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final r = entry.row;
    // The driver taps a past session by its start time ("YYYY-MM-DD HH:MM").
    return SpokenLabel(
      semanticLabel: '${r.started} · ${r.subject}',
      button: true,
      onTap: onTap,
      child: Card(
        child: ListTile(
          onTap: onTap,
          // Wrap: a long subject drops under the date instead of overflowing.
          title: Wrap(
            spacing: AppSpacing.sm,
            children: [Text(r.started), ContentText(r.subject)],
          ),
          subtitle: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (final c in r.cards)
                Row(
                  children: [
                    if (c.done)
                      const Icon(Icons.check, size: AppTextSize.label),
                    Flexible(child: ContentText(c.front)),
                  ],
                ),
              Wrap(
                spacing: AppSpacing.md,
                children: [
                  GlyphStat(Icons.timer_outlined, '${r.activeMinutes}'),
                  GlyphStat(Icons.bolt, '${r.creditedMinutes}'),
                ],
              ),
            ],
          ),
          trailing: entry.hidden
              ? SpokenLabel(
                  semanticLabel: r.autoArchived
                      ? 'archived: no reply'
                      : 'archived',
                  child: Icon(
                    r.autoArchived
                        ? Icons.comments_disabled_outlined
                        : Icons.inventory_2_outlined,
                    color: AppPalette.warning,
                  ),
                )
              : const Icon(Icons.chevron_right),
          contentPadding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
        ),
      ),
    );
  }
}
