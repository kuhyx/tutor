/// One module of an approved plan on the Plan screen.
library;

import 'package:flutter/material.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/progress/card_progress.dart';

/// An approved plan's module: status, card count, recall; Retry if failed.
class ModuleProgressTile extends StatelessWidget {
  /// Creates the tile.
  const new({
    required this.module,
    required this.onRetry,
    this.tally,
    super.key,
  });

  /// The module.
  final Module module;

  /// Its cards: done / mastered / due (null until the log is folded).
  final Tally? tally;

  /// Asks the worker to try generating again.
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final m = module;
    final failed = m.status == ModuleStatus.failed;
    return Card(
      child: ListTile(
        title: Text(m.title),
        subtitle: Text(
          [
            m.status.name,
            if (m.cards > 0) '${m.cards} cards',
            if (tally != null && tally!.cards > 0) tally!.doneText,
            'recall ${(m.recall * 100).round()}%',
            if (failed && m.error != null) m.error!,
          ].join(' · '),
        ),
        trailing: failed
            ? TextButton(onPressed: onRetry, child: const Text('Retry'))
            : null,
      ),
    );
  }
}
