/// The Session's side panel (`index.html` aside) on narrow windows and the
/// phone (a drawer): target card, the card actions, known concepts.
/// Text-free: glyph buttons (the old wording is their spoken label); the
/// subject, card and concept names are content.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/session/session_bar.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// Side panel.
class SessionSide extends StatelessWidget {
  /// Creates the panel.
  const new({
    required this.meta,
    required this.subject,
    required this.mastered,
    required this.actions,
    super.key,
  });

  /// Session meta (null before it arrives).
  final SessionMeta? meta;

  /// The session's subject, when cached.
  final SubjectData? subject;

  /// Known concept names (the wire's `mastered`), oldest first.
  final List<String> mastered;

  /// The card action glyphs.
  final CardActions actions;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final m = meta;
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.md),
      children: [
        if (subject != null) ...[
          ContentText(subject!.meta.title, style: text.titleMedium),
          const SizedBox(height: AppSpacing.md),
        ],
        Row(
          children: [
            const SpokenLabel(
              semanticLabel: 'Target card',
              child: Icon(Icons.gps_fixed, size: AppTextSize.body),
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(child: ContentText(m?.card?.front ?? '-')),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: actions.glyphs(),
        ),
        const SizedBox(height: AppSpacing.lg),
        // Known concepts: a glyph, the count, the names (content).
        knownCount(mastered),
        const SizedBox(height: AppSpacing.xs),
        for (final c in mastered.reversed) ContentText('• $c'),
      ],
    );
  }
}

/// Known concept names of [subject] plus those [view]'s turns marked, oldest
/// first.
List<String> masteredOf(SubjectData? subject, SessionView? view) => <String>{
  ...?subject?.concepts.map((c) => c.name),
  for (final m in view?.messages ?? const <KeyedMessage>[])
    ...m.message.masteredNew,
}.toList();

/// The card actions of [view] (of [subject]): requests go through [run].
CardActions cardActionsFor(
  BuildContext context,
  TutorServices s,
  SubjectData? subject,
  SessionView? view,
  Future<Object?> Function(RequestBody body) run,
) {
  final meta = view?.meta;
  final live = meta != null && !meta.stopped;
  return CardActions(
    onSwitch: subject == null ? null : () => switchCard(context, subject, run),
    onMarkDone: live && meta.card != null && !meta.cardDone
        ? () => run(RequestBody.cardDone(meta.subject, meta.card!.id))
        : null,
    // Card done: CardEnd offers Stop here instead.
    onStop: live && !meta.cardDone
        ? () => run(RequestBody.stop(view!.sid))
        : null,
    onEdit: () => openEditor(context, s, subject: meta?.subject),
    onReport: () =>
        showReport(context, s, route: '/session', session: view?.sid),
    onHistory: () => openHistory(context, s),
  );
}

/// Switch card: picks a card of [subject] and starts it through [run].
Future<void> switchCard(
  BuildContext context,
  SubjectData subject,
  Future<Object?> Function(RequestBody body) run,
) async {
  final card = await pickCard(context, subject);
  if (card != null) {
    await run(RequestBody.sessionStart(subject: subject.id, card: card));
  }
}

/// Picks a card of [subject] to start a session on (module order, then
/// card order). Null when dismissed.
Future<String?> pickCard(BuildContext context, SubjectData subject) =>
    showDialog<String>(
      context: context,
      builder: (context) => SimpleDialog(
        children: [
          for (final m in subject.plan?.modules ?? const <Module>[])
            for (final e in subject.cardsOf(m.id))
              SimpleDialogOption(
                onPressed: () => Navigator.pop(context, e.key),
                child: ContentText('${m.title}: ${e.value.front}'),
              ),
        ],
      ),
    );
