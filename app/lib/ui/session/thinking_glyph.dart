/// The tutor's trace as parts: the thinking head (a toggle with the
/// research count), the steps under it, and their wording.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/trace.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// One tool call as a line: `Search: <query>`, `Fetch: <url>`, `Run: <cmd>`.
String toolLine(TraceStep step) {
  final verb = switch (step.name) {
    'WebSearch' => 'Search',
    'WebFetch' => 'Fetch',
    'Bash' => 'Run',
    _ => step.name,
  };
  return step.input.isEmpty ? verb : '$verb: ${step.input}';
}

/// The panel's header: `Thinking`, plus how many research steps it holds.
String traceHeader(List<TraceStep> steps) {
  final n = steps.where((s) => s.isTool).length;
  return n == 0
      ? 'Thinking'
      : 'Thinking · $n research step${n == 1 ? '' : 's'}';
}

/// Panels start open (the fixture's `&open=1`, for screenshots).
bool debugThinkingOpen = false;

IconData _icon(String name) => switch (name) {
  'WebSearch' => Icons.search,
  'WebFetch' => Icons.public,
  'Bash' => Icons.terminal,
  _ => Icons.build_outlined,
};

/// The thinking head with its research count: a toggle (no chevron, no
/// rule), spoken as [traceHeader].
class ThinkingGlyph extends StatelessWidget {
  /// Creates the glyph for [steps]; [open] is its expanded state.
  const new({
    required this.steps,
    required this.open,
    required this.onToggle,
    this.leading,
    super.key,
  });

  /// The steps, in order.
  final List<TraceStep> steps;

  /// The thinking shows.
  final bool open;

  /// Opens or folds it.
  final VoidCallback onToggle;

  /// Drawn before the head (the live panel's chevron).
  final Widget? leading;

  @override
  Widget build(BuildContext context) {
    final muted = Theme.of(context).colorScheme.onSurfaceVariant;
    final research = steps.where((s) => s.isTool).length;
    return SpokenLabel(
      button: true,
      expanded: open,
      semanticLabel: traceHeader(steps),
      onTap: onToggle,
      child: InkWell(
        borderRadius: BorderRadius.circular(AppRadius.sm),
        onTap: onToggle,
        child: Padding(
          // The live panel's header keeps its old, flush-left padding.
          padding: leading == null
              ? const EdgeInsets.all(AppSpacing.xs)
              : const EdgeInsets.symmetric(vertical: AppSpacing.xs),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (leading case final l?) ...[
                l,
                const SizedBox(width: AppSpacing.xs),
              ],
              Icon(Icons.psychology_outlined, size: 18, color: muted),
              if (research > 0) ...[
                const SizedBox(width: AppSpacing.xs),
                CountBadge(research, icon: Icons.search),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// The trace's steps, one under the other.
class ThinkingBody extends StatelessWidget {
  /// Creates the list of [steps].
  const new(this.steps, {super.key});

  /// The steps shown.
  final List<TraceStep> steps;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [for (final s in steps) _StepView(s)],
  );
}

class _StepView extends StatelessWidget {
  const new(this.step);

  final TraceStep step;

  @override
  Widget build(BuildContext context) {
    final muted = Theme.of(context).colorScheme.onSurfaceVariant;
    final style = Theme.of(context).textTheme.bodySmall?.copyWith(color: muted);
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.xs),
      child: step.isTool
          ? Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(_icon(step.name), size: 16, color: muted),
                const SizedBox(width: AppSpacing.xs),
                // The verb is the glyph; the query, url or command is content.
                Expanded(
                  child: ContentText(
                    step.input.isEmpty ? '' : step.input,
                    style: style,
                  ),
                ),
              ],
            )
          : ContentText(step.text.trim(), style: style),
    );
  }
}
