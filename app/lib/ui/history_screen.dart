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

  void _reload() => setState(() => _lists = _load());

  Future<void> _open(String sid) async {
    await openTranscript(context, widget.services, sid);
    if (mounted) _reload();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('History'),
      actions: [
        IconButton(
          tooltip: 'Reload',
          onPressed: _reload,
          icon: const Icon(Icons.refresh),
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
          return PageList(children: [Text('Could not load: ${snap.error}')]);
        }
        final lists = snap.requireData;
        return PageList(
          children: [
            if (lists.shown.isEmpty)
              const EmptyState(
                icon: Icons.history,
                title: 'No past sessions',
                message: 'Sessions appear here once started.',
              ),
            for (final e in lists.shown)
              _Row(entry: e, onTap: () => unawaited(_open(e.sid))),
            if (lists.hidden.isNotEmpty)
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton(
                  onPressed: () =>
                      setState(() => _showArchived = !_showArchived),
                  child: Text(
                    '${_showArchived ? 'Hide' : 'Show'} archived '
                    '(${lists.hidden.length})',
                  ),
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

class _Row extends StatelessWidget {
  const new({required this.entry, required this.onTap});

  final HistoryEntry entry;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final r = entry.row;
    final cards = r.cards
        .map((c) => '${c.done ? '✓ ' : ''}${c.front}')
        .join('\n');
    return Card(
      child: ListTile(
        onTap: onTap,
        title: Text('${r.started} · ${r.subject}'),
        subtitle: Text(
          [
            if (cards.isNotEmpty) cards,
            '${r.activeMinutes} min active · ${r.creditedMinutes} credited',
          ].join('\n'),
        ),
        trailing: entry.hidden
            ? Pill(r.autoArchived ? 'archived: no reply' : 'archived')
            : const Icon(Icons.chevron_right),
        contentPadding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
      ),
    );
  }
}
