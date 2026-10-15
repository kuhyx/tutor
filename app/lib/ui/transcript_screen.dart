/// A past session, read-only (`static/session.js` showPast): its cards with
/// Mark done / Mark not done, Archive / Unarchive, Repeat (a new session on
/// its first card) and Continue (`session_resume`).
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/history/history.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/limit_switch.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/session/message_tile.dart';

/// The transcript screen.
class TranscriptScreen extends StatefulWidget {
  /// Creates the screen.
  const new({required this.services, required this.sid, super.key});

  /// Services.
  final TutorServices services;

  /// Session id.
  final String sid;

  @override
  State<TranscriptScreen> createState() => _TranscriptScreenState();
}

class _TranscriptScreenState extends State<TranscriptScreen> {
  late final RequestRunner _runner = RequestRunner(widget.services.relay);
  late Future<(Transcript, HistoryEntry?)> _data = _load();
  late final VoidCallback _unwatch;

  TutorServices get _s => widget.services;

  Future<(Transcript, HistoryEntry?)> _load() async {
    final t = await _s.history.transcript(widget.sid);
    final rows = await _s.history.load();
    final row = rows.where((r) => r.sid == widget.sid).firstOrNull;
    return (t, row);
  }

  @override
  void initState() {
    super.initState();
    // Claude out: the model-free drill takes over.
    _unwatch = switchToDrillOnLimit(this, _s, _runner);
  }

  @override
  void dispose() {
    _unwatch();
    unawaited(_runner.dispose());
    super.dispose();
  }

  void _reload() => setState(() {
    _data = _load()..ignore(); // FutureBuilder reports errors
  });

  Future<void> _toSession(RequestBody body) async {
    final status = await _runner.run(body);
    if (status is RelayDone && mounted) {
      await openSession(context, _s, replace: true);
    }
  }

  Future<void> _archive(bool archived) async {
    await _s.history.setArchived(widget.sid, archived: archived);
    _reload();
  }

  Future<void> _mark(String subject, String card, bool done) async {
    await _runner.run(RequestBody.cardDone(subject, card, done: done));
    if (mounted) _reload();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Past session')),
    body: FutureBuilder<(Transcript, HistoryEntry?)>(
      future: _data,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          return PageList(children: [Text('Could not load: ${snap.error}')]);
        }
        final (t, entry) = snap.requireData;
        final row = entry?.row;
        final subject = row?.subject ?? t.view.meta?.subject;
        final first = row?.cards.firstOrNull?.id ?? t.view.meta?.card?.id;
        final text = Theme.of(context).textTheme;
        return PageList(
          children: [
            Text('${widget.sid} - read-only', style: text.titleMedium),
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                if (t.archived || (row?.autoArchived ?? false))
                  Pill(
                    row?.autoArchived ?? false
                        ? 'archived: no reply'
                        : 'archived',
                  ),
                if (!(row?.autoArchived ?? false))
                  OutlinedButton(
                    onPressed: () => _archive(!t.archived),
                    child: Text(t.archived ? 'Unarchive' : 'Archive'),
                  ),
                if (first != null)
                  FilledButton(
                    onPressed: () => _toSession(
                      RequestBody.sessionStart(subject: subject, card: first),
                    ),
                    child: const Text('Repeat'),
                  ),
                OutlinedButton(
                  onPressed: () =>
                      _toSession(RequestBody.sessionResume(widget.sid)),
                  child: const Text('Continue'),
                ),
              ],
            ),
            RequestStatusLine(_runner),
            if (row != null && subject != null)
              for (final c in row.cards)
                CheckboxListTile(
                  value: c.done,
                  title: Text(c.front),
                  subtitle: Text(c.doneHere ? 'done in this session' : ''),
                  onChanged: (on) => _mark(subject, c.id, on ?? false),
                ),
            Text(
              'Active ${row?.activeMinutes ?? 0} min · credited '
              '${row?.creditedMinutes ?? t.view.meta?.creditedMinutes ?? 0}',
              style: text.bodySmall,
            ),
            const Divider(),
            for (final m in t.view.messages) MessageTile(message: m.message),
          ],
        );
      },
    ),
  );
}
