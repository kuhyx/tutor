/// The Session's side panel (`index.html` aside): target card, Switch card,
/// Mark card done, Edit cards, Report a problem, mastered concepts.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/session.dart';

/// Side panel.
class SessionSide extends StatelessWidget {
  /// Creates the panel.
  const new({
    required this.meta,
    required this.subject,
    required this.mastered,
    required this.onSwitch,
    required this.onMarkDone,
    required this.onEdit,
    required this.onReport,
    required this.onHistory,
    super.key,
  });

  /// Session meta (null before it arrives).
  final SessionMeta? meta;

  /// The session's subject, when cached.
  final SubjectData? subject;

  /// Mastered concept names, oldest first.
  final List<String> mastered;

  /// Start another card instead.
  final VoidCallback? onSwitch;

  /// Count the live card as done.
  final VoidCallback? onMarkDone;

  /// Open the card editor.
  final VoidCallback onEdit;

  /// Report a problem with the whole experience.
  final VoidCallback onReport;

  /// Open History.
  final VoidCallback onHistory;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final m = meta;
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.md),
      children: [
        if (subject != null) ...[
          Text(subject!.meta.title, style: text.titleMedium),
          const SizedBox(height: AppSpacing.md),
        ],
        Text('Target card', style: text.labelLarge),
        const SizedBox(height: AppSpacing.xs),
        Text(m?.card?.front ?? '-'),
        const SizedBox(height: AppSpacing.md),
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            OutlinedButton(
              onPressed: onSwitch,
              child: const Text('Switch card'),
            ),
            OutlinedButton(
              onPressed: onMarkDone,
              child: const Text('Mark card done'),
            ),
            OutlinedButton(onPressed: onEdit, child: const Text('Edit cards')),
            OutlinedButton(onPressed: onHistory, child: const Text('History')),
            TextButton(
              onPressed: onReport,
              child: const Text('Report a problem'),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.lg),
        Text('Mastered', style: text.labelLarge),
        const SizedBox(height: AppSpacing.xs),
        if (mastered.isEmpty) const Text('-'),
        for (final c in mastered.reversed) Text('• $c'),
      ],
    );
  }
}

/// Picks a card of [subject] to start a session on (module order, then
/// card order). Null when dismissed.
Future<String?> pickCard(BuildContext context, SubjectData subject) =>
    showDialog<String>(
      context: context,
      builder: (context) => SimpleDialog(
        title: const Text('Switch card'),
        children: [
          for (final m in subject.plan?.modules ?? const <Module>[])
            for (final e in subject.cardsOf(m.id))
              SimpleDialogOption(
                onPressed: () => Navigator.pop(context, e.key),
                child: Text('${m.title}: ${e.value.front}'),
              ),
        ],
      ),
    );
