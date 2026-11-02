/// Today's parts: the progress dots and the current step's card.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/plan/today_plan.dart';

/// One dot per step: done, current, to do.
class PlanDots extends StatelessWidget {
  /// Creates the dots.
  const new(this.plan, {super.key});

  /// The plan.
  final TodayPlan plan;

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    final current = plan.current;
    return Wrap(
      key: const ValueKey('today-dots'),
      spacing: AppSpacing.sm,
      children: [
        for (final s in plan.steps)
          Container(
            width: 14,
            height: 14,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: s.done
                  ? color.primary
                  : (s == current ? color.secondary : color.outlineVariant),
            ),
          ),
      ],
    );
  }
}

/// The current step: title, what to do, Start and Done.
class StepCard extends StatelessWidget {
  /// Creates the card.
  const new({
    required this.step,
    required this.number,
    required this.total,
    required this.busy,
    required this.onStart,
    required this.onDone,
    super.key,
  });

  /// The step.
  final PlanStep step;

  /// Its 1-based position.
  final int number;

  /// Steps in the plan.
  final int total;

  /// A Done request is in flight.
  final bool busy;

  /// Start pressed.
  final VoidCallback onStart;

  /// Done pressed.
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Step $number of $total', style: text.labelLarge),
            const SizedBox(height: AppSpacing.sm),
            Text(
              step.title,
              key: const ValueKey('today-title'),
              style: text.headlineSmall,
            ),
            const SizedBox(height: AppSpacing.md),
            Text(step.what, style: text.bodyLarge),
            const SizedBox(height: AppSpacing.lg),
            if (step.kind != StepKind.note)
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  key: const ValueKey('today-start'),
                  onPressed: onStart,
                  child: Text(AppLocalizations.of(context).start),
                ),
              ),
            const SizedBox(height: AppSpacing.sm),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                key: const ValueKey('today-done'),
                onPressed: busy ? null : onDone,
                child: const Text('Done → next'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
