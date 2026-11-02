import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/mock/mock_links.dart';
import 'package:tutor/mock/mock_models.dart';
import 'package:tutor/mock/mock_result_detail.dart';
import 'package:tutor/mock/mock_session.dart';

/// Score, per-task breakdown, and a study button on every missed item.
class MockResultScreen extends StatelessWidget {
  /// Creates the screen over a finished [session].
  const new({
    required this.services,
    required this.session,
    required this.links,
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// The finished test.
  final MockSession session;

  /// Where the study buttons go.
  final MockLinks links;

  Future<void> _done(BuildContext context) async {
    await discardMockSession(services.kv);
    if (context.mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final r = session.result!;
    final score = '${r.score}/${r.total}';
    final percent = '${r.percent}%';
    return Scaffold(
      appBar: AppBar(
        title: Text(score, key: const ValueKey('score')),
        actions: [
          Center(child: Text(percent, key: const ValueKey('percent'))),
          IconButton(
            key: const ValueKey('done'),
            onPressed: () => unawaited(_done(context)),
            icon: const Icon(Icons.check, semanticLabel: 'Done'),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          children: [
            for (final item in r.items)
              ExpansionTile(
                key: ValueKey('item-${item.id}'),
                initiallyExpanded: !item.correct,
                leading: Icon(
                  item.correct ? Icons.check_circle : Icons.cancel,
                  color: item.correct ? AppPalette.success : AppPalette.danger,
                ),
                title: Text(item.title),
                subtitle: item.topic.isEmpty ? null : Text(item.topic),
                childrenPadding: const EdgeInsets.all(AppSpacing.md),
                expandedCrossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  mockItemDetail(item),
                  if (!item.correct && item.link != null)
                    _StudyButton(item, links),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class _StudyButton extends StatelessWidget {
  const new(this.item, this.links);

  final MockItem item;
  final MockLinks links;

  @override
  Widget build(BuildContext context) {
    final link = item.link!;
    final lesson = link.kind == 'lesson';
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.sm),
      child: FilledButton.tonal(
        key: ValueKey('study-${item.id}'),
        onPressed: () => unawaited(
          lesson
              ? links.openLesson(context, link.target)
              : links.openCoach(context, link.target),
        ),
        child: Icon(
          lesson ? Icons.school_outlined : Icons.psychology_outlined,
          semanticLabel: lesson ? 'Lesson' : 'Coach',
        ),
      ),
    );
  }
}
