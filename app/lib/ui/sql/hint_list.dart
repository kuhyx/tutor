/// The hint questions so far, oldest first, as a chat-style list.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// One bubble per hint question.
class HintList extends StatelessWidget {
  /// Creates the list.
  const new(this.hints, {super.key});

  /// Hint questions.
  final List<String> hints;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final h in hints)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: scheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(AppRadius.md),
              ),
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.lightbulb_outline, semanticLabel: 'Hint'),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(child: SelectableText(h)),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }
}
