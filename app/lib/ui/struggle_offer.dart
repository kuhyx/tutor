/// Review's "Struggling with this card?" offer (DOCS-contract-struggle §4):
/// a panel under the queue, never a modal, so ratings and keys go on.
/// "Get help" asks the PC for a struggle session (greyed out "PC offline"
/// while the worker is silent); Dismiss records nothing.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/review/review_session.dart';
import 'package:tutor/ui/common.dart';

/// The offer for [item].
class StruggleOffer extends StatelessWidget {
  /// Creates the panel.
  const new({
    required this.item,
    required this.presence,
    required this.runner,
    required this.onHelp,
    required this.onDismiss,
    super.key,
  });

  /// The struggling card.
  final ReviewItem item;

  /// PC presence ("Get help" needs the worker).
  final ValueNotifier<PcPresence> presence;

  /// Runs the `session_start`; its status shows here.
  final RequestRunner runner;

  /// Get help.
  final VoidCallback onHelp;

  /// Dismiss.
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Center(
      heightFactor: 1,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: kPageMaxWidth),
        child: Card(
          margin: const EdgeInsets.all(AppSpacing.md),
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Struggling with this card?', style: text.titleMedium),
                Text(item.card.front, style: text.bodySmall),
                const SizedBox(height: AppSpacing.sm),
                Wrap(
                  spacing: AppSpacing.sm,
                  runSpacing: AppSpacing.sm,
                  children: [
                    ValueListenableBuilder<PcPresence>(
                      valueListenable: presence,
                      builder: (context, value, _) =>
                          value == PcPresence.offline
                          ? const FilledButton(
                              onPressed: null,
                              child: Text('PC offline'),
                            )
                          : FilledButton(
                              onPressed: onHelp,
                              child: const Text('Get help'),
                            ),
                    ),
                    TextButton(
                      onPressed: onDismiss,
                      child: const Text('Dismiss'),
                    ),
                  ],
                ),
                RequestStatusLine(runner),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
