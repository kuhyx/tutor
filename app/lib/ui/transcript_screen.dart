/// A past session, read-only (`static/session.js` showPast): its cards with
/// Mark done / Mark not done, Archive / Unarchive, Repeat (a new session on
/// its first card), Continue (`session_resume`) and, when its card was done
/// in it, Ask a follow-up (`follow_up_box.dart`).
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
import 'package:tutor/ui/follow_up_box.dart';
import 'package:tutor/ui/limit_switch.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/session/blocked_panel.dart';
import 'package:tutor/ui/session/message_tile.dart';
import 'package:tutor/util/device.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/spoken_label.dart';

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
    final status = await _runner.run(body.withDevice(deviceName));
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
    appBar: AppBar(),
    body: FutureBuilder<(Transcript, HistoryEntry?)>(
      future: _data,
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
        final (t, entry) = snap.requireData;
        final row = entry?.row;
        final subject = row?.subject ?? t.view.meta?.subject;
        final first = row?.cards.firstOrNull?.id ?? t.view.meta?.card?.id;
        final doneHere =
            (row?.cards.any((c) => c.doneHere) ?? false) ||
            (t.view.meta?.cardDone ?? false);
        final autoArchived = row?.autoArchived ?? false;
        final meta = t.view.meta;
        return PageList(
          children: [
            Row(
              children: [
                // Read-only: a lock beside the session id (content).
                const SpokenLabel(
                  semanticLabel: 'Read-only',
                  child: Icon(Icons.lock_outline),
                ),
                const SizedBox(width: AppSpacing.sm),
                IdChip(widget.sid),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                if (t.archived || autoArchived)
                  SpokenLabel(
                    semanticLabel: autoArchived
                        ? 'archived: no reply'
                        : 'archived',
                    child: Icon(
                      autoArchived
                          ? Icons.comments_disabled_outlined
                          : Icons.inventory_2_outlined,
                      color: AppPalette.warning,
                    ),
                  ),
                if (!autoArchived)
                  GlyphButton(
                    icon: t.archived
                        ? Icons.unarchive_outlined
                        : Icons.archive_outlined,
                    semanticLabel: t.archived ? 'Unarchive' : 'Archive',
                    onPressed: () => _archive(!t.archived),
                  ),
                if (first != null)
                  GlyphButton(
                    icon: Icons.replay,
                    semanticLabel: 'Repeat',
                    filled: true,
                    onPressed: () => _toSession(
                      RequestBody.sessionStart(subject: subject, card: first),
                    ),
                  ),
                GlyphButton(
                  icon: Icons.play_arrow,
                  semanticLabel: 'Continue',
                  tint: Theme.of(context).colorScheme.primary,
                  onPressed: () =>
                      _toSession(RequestBody.sessionResume(widget.sid)),
                ),
              ],
            ),
            if (doneHere) ...[
              const SizedBox(height: AppSpacing.sm),
              FollowUpBox(
                sid: widget.sid,
                runner: _runner,
                onAsked: () => openSession(context, _s, replace: true),
              ),
            ],
            // A blocked Repeat (locked, cap) shows its call to action.
            ValueListenableBuilder<RelayStatus?>(
              valueListenable: _runner.status,
              builder: (context, st, _) => st is RelayFailed && st.blocks
                  ? BlockedPanel(
                      services: _s,
                      blocked: st.blocked!,
                      text: st.text,
                      subject: subject,
                      lastBody: _runner.lastBody,
                      onRun: (body) async {
                        await _toSession(body);
                        return _runner.status.value!;
                      },
                    )
                  : RequestStatusLine(_runner),
            ),
            if (row != null && subject != null)
              for (final c in row.cards)
                CheckboxListTile(
                  value: c.done,
                  title: ContentText(c.front),
                  secondary: c.doneHere
                      ? const SpokenLabel(
                          semanticLabel: 'done in this session',
                          child: Icon(Icons.task_alt),
                        )
                      : null,
                  onChanged: (on) => _mark(subject, c.id, on ?? false),
                ),
            Wrap(
              spacing: AppSpacing.md,
              children: [
                SpokenLabel(
                  semanticLabel: 'Active minutes',
                  child: GlyphStat(
                    Icons.timer_outlined,
                    '${row?.activeMinutes ?? 0}',
                  ),
                ),
                SpokenLabel(
                  semanticLabel: 'Credited minutes',
                  child: GlyphStat(
                    Icons.bolt,
                    '${row?.creditedMinutes ?? meta?.creditedMinutes ?? 0}',
                  ),
                ),
              ],
            ),
            const Divider(),
            for (final m in t.view.messages) MessageTile(message: m.message),
          ],
        );
      },
    ),
  );
}
