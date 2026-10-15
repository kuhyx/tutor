/// Home's content: today's counters, review and session entry points,
/// subjects, and "I want to learn...".
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/home/home_loader.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/progress/progress.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/session/session_entry.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/layout.dart';
import 'package:tutor/ui/new_subject_field.dart';

/// Home's body.
class HomeBody extends StatelessWidget {
  /// Creates the body.
  const new({
    required this.data,
    required this.presence,
    required this.runner,
    required this.onReview,
    required this.onDrill,
    required this.onSession,
    required this.onPlan,
    required this.onEdit,
    required this.onPick,
    required this.onNewSubject,
    required this.onFinish,
    super.key,
  });

  /// Snapshot.
  final HomeSnapshot data;

  /// PC presence.
  final ValueNotifier<PcPresence> presence;

  /// Runs subject requests.
  final RequestRunner runner;

  /// Opens Review.
  final VoidCallback onReview;

  /// Opens Review in Drill mode (pick-an-answer, no model).
  final VoidCallback onDrill;

  /// Opens the Session for Home's button.
  final ValueChanged<SessionEntry> onSession;

  /// Opens a subject's plan.
  final ValueChanged<String> onPlan;

  /// Opens a subject's cards.
  final ValueChanged<String> onEdit;

  /// Picks the subject new material comes from.
  final ValueChanged<String> onPick;

  /// Sends "I want to learn...".
  final ValueChanged<String> onNewSubject;

  /// Completed subject: go deeper or review only.
  final void Function(String subject, {required bool goDeeper}) onFinish;

  @override
  Widget build(BuildContext context) {
    final today = data.today;
    final entry = sessionEntry(data.live, data.currentSubject);
    final text = Theme.of(context).textTheme;
    // Wide: today on the left; subjects and a new one on the right.
    return TwoColumnPage(
      secondFlex: 3,
      firstFlex: 2,
      first: [
        if (data.offline)
          const Card(
            child: ListTile(
              leading: Icon(Icons.cloud_off),
              title: Text('Offline: showing the last synced catalog'),
            ),
          ),
        PcOfflineBanner(presence),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Today', style: text.titleMedium),
                const SizedBox(height: AppSpacing.sm),
                if (today == null)
                  const Text('No counters yet (the PC writes them).')
                else ...[
                  Text(
                    'Credited ${today.creditedMinutes}/${today.target} min'
                    '${_active(today.activeMinutes)}'
                    ' · new cards ${today.newCards}/${today.newCap}',
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  LinearProgressIndicator(
                    value: today.target == 0
                        ? 0
                        : (today.creditedMinutes / today.target).clamp(0, 1),
                  ),
                ],
                const SizedBox(height: AppSpacing.md),
                Wrap(
                  spacing: AppSpacing.sm,
                  runSpacing: AppSpacing.sm,
                  children: [
                    FilledButton.icon(
                      onPressed: () => onSession(entry),
                      icon: const Icon(Icons.chat_bubble_outline),
                      label: Text(entry.label),
                    ),
                    OutlinedButton.icon(
                      onPressed: onReview,
                      icon: const Icon(Icons.style),
                      label: Text('Review (${data.due} due)'),
                    ),
                    OutlinedButton.icon(
                      onPressed: onDrill,
                      icon: const Icon(Icons.touch_app_outlined),
                      label: const Text('Drill'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ],
      second: [
        const SectionHeader('Subjects'),
        if (data.subjects.isEmpty)
          const EmptyState(
            icon: Icons.lightbulb_outline,
            title: 'No subjects yet',
            message: 'Say what you want to learn below.',
          ),
        for (final s in data.subjects)
          _SubjectTile(
            entry: s,
            current: s.id == data.currentSubject,
            onPlan: () => onPlan(s.id),
            onEdit: () => onEdit(s.id),
            onPick: () => onPick(s.id),
            onFinish: (goDeeper) => onFinish(s.id, goDeeper: goDeeper),
            onRetry: () => onNewSubject(s.meta.goal),
          ),
        const SectionHeader('New subject'),
        NewSubjectField(runner: runner, onSubmit: onNewSubject),
      ],
    );
  }
}

class _SubjectTile extends StatelessWidget {
  const new({
    required this.entry,
    required this.current,
    required this.onPlan,
    required this.onEdit,
    required this.onPick,
    required this.onFinish,
    required this.onRetry,
  });

  final SubjectEntry entry;
  final bool current;
  final VoidCallback onPlan;
  final VoidCallback onEdit;
  final VoidCallback onPick;
  final ValueChanged<bool> onFinish;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final status = entry.meta.status;
    final data = entry.data;
    final (mastered, total) = data == null ? (0, 0) : masteredOf(data);
    final teaching =
        status == SubjectStatus.active || status == SubjectStatus.completed;
    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ListTile(
            leading: Icon(
              current ? Icons.radio_button_checked : Icons.radio_button_off,
            ),
            title: Text(entry.meta.title),
            subtitle: Text(
              [
                status.wire.replaceAll('_', ' '),
                if (total > 0) '$mastered/$total modules mastered',
                if (current) 'new material from here',
                ?entry.meta.error,
              ].join(' · '),
            ),
            onTap: teaching && !current ? onPick : onPlan,
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.md,
              0,
              AppSpacing.md,
              AppSpacing.sm,
            ),
            child: Wrap(
              spacing: AppSpacing.sm,
              children: [
                TextButton(onPressed: onPlan, child: const Text('Plan')),
                if (data != null && data.cards.isNotEmpty)
                  TextButton(onPressed: onEdit, child: const Text('Cards')),
                if (teaching && !current)
                  TextButton(
                    onPressed: onPick,
                    child: const Text('Learn this next'),
                  ),
                if (status == SubjectStatus.failed &&
                    entry.meta.goal.isNotEmpty)
                  TextButton(
                    onPressed: onRetry,
                    child: const Text('Try again'),
                  ),
                if (status == SubjectStatus.completed) ...[
                  TextButton(
                    onPressed: () => onFinish(true),
                    child: const Text('Go deeper'),
                  ),
                  TextButton(
                    onPressed: () => onFinish(false),
                    child: const Text('Review only'),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

String _active(int? minutes) => minutes == null ? '' : ' · $minutes min active';
