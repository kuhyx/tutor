/// Today's parts: the progress dots and the current step's card.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/plan/today_plan.dart';
import 'package:tutor/widgets/content_text.dart';

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
    this.actions = true,
    super.key,
  });

  /// The step.
  final PlanStep step;

  /// Start and Done inside the card; false where the page pins them.
  final bool actions;

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
    final l10n = AppLocalizations.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.stepOf(number, total), style: text.labelLarge),
            const SizedBox(height: AppSpacing.sm),
            ContentText(
              step.title,
              key: const ValueKey('today-title'),
              style: text.headlineSmall,
            ),
            const SizedBox(height: AppSpacing.md),
            ContentText(step.what, style: text.bodyLarge),
            if (actions) ...[
              const SizedBox(height: AppSpacing.lg),
              StepActions(
                step: step,
                busy: busy,
                onStart: onStart,
                onDone: onDone,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Start (not for a note) and Done, full width.
class StepActions extends StatelessWidget {
  /// Creates the buttons.
  const new({
    required this.step,
    required this.busy,
    required this.onStart,
    required this.onDone,
    super.key,
  });

  /// The step.
  final PlanStep step;

  /// A Done request is in flight.
  final bool busy;

  /// Start pressed.
  final VoidCallback onStart;

  /// Done pressed.
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (step.kind != StepKind.note)
          FilledButton(
            key: const ValueKey('today-start'),
            onPressed: onStart,
            child: Text(l10n.start),
          ),
        const SizedBox(height: AppSpacing.sm),
        OutlinedButton(
          key: const ValueKey('today-done'),
          onPressed: busy ? null : onDone,
          child: Text(l10n.doneStep),
        ),
      ],
    );
  }
}
