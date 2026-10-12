/// One module of an approved plan on the Plan screen.
library;

import 'package:flutter/material.dart';
import 'package:tutor/model/plan.dart';

/// An approved plan's module: status, card count, recall; Retry if failed.
class ModuleProgressTile extends StatelessWidget {
  /// Creates the tile.
  const new({required this.module, required this.onRetry, super.key});

  /// The module.
  final Module module;

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
