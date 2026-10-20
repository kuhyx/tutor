/// The tutor's thinking and research (DOCS-contract §6 `trace` / `progress`):
/// a folded "Thinking" panel under each tutor bubble, and, while a turn is
/// in flight, the busy line with the research steps appearing as they
/// happen (the reasoning itself stays folded until opened).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/model/trace.dart';
import 'package:tutor/relay/error_text.dart';

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

/// A collapsible trace; folded by default.
class ThinkingPanel extends StatefulWidget {
  /// Creates the panel. [live]: a turn in flight, whose research steps show
  /// even while folded.
  const new({required this.steps, this.live = false, super.key});

  /// The steps, in order.
  final List<TraceStep> steps;

  /// The turn is still running.
  final bool live;

  @override
  State<ThinkingPanel> createState() => _ThinkingPanelState();
}

class _ThinkingPanelState extends State<ThinkingPanel> {
  bool _open = debugThinkingOpen;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final muted = scheme.onSurfaceVariant;
    final steps = widget.steps;
    final shown = _open
        ? steps
        : (widget.live
              ? steps.where((s) => s.isTool).toList()
              : const <TraceStep>[]);
    return Container(
      margin: const EdgeInsets.only(top: AppSpacing.sm),
      padding: const EdgeInsets.only(left: AppSpacing.sm),
      decoration: BoxDecoration(
        border: Border(
          left: BorderSide(color: scheme.outlineVariant, width: 2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Semantics(
            button: true,
            expanded: _open,
            child: InkWell(
              borderRadius: BorderRadius.circular(AppRadius.sm),
              onTap: () => setState(() => _open = !_open),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      _open ? Icons.expand_less : Icons.expand_more,
                      size: 18,
                      color: muted,
                    ),
                    const SizedBox(width: AppSpacing.xs),
                    Text(
                      traceHeader(steps),
                      style: Theme.of(context).textTheme.labelMedium
                          ?.copyWith(color: muted),
                    ),
                  ],
                ),
              ),
            ),
          ),
          for (final s in shown) _StepView(s),
        ],
      ),
    );
  }
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
                Expanded(child: Text(toolLine(step), style: style)),
              ],
            )
          : Text(step.text.trim(), style: style),
    );
  }
}

/// The busy line of a turn in flight, with its trace so far. Key it by the
/// request id so an opened panel stays open across updates.
class LiveTrace extends StatelessWidget {
  /// Creates the line.
  const new({required this.phase, this.steps = const [], super.key});

  /// Worker phase.
  final Phase phase;

  /// The request's steps so far (`progress`).
  final List<TraceStep> steps;

  @override
  Widget build(BuildContext context) {
    final researching = phase == Phase.thinking && steps.any((s) => s.isTool);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(researching ? 'Researching...' : phaseText(phase)),
        if (steps.isNotEmpty) ThinkingPanel(steps: steps, live: true),
      ],
    );
  }
}

/// The busy line of [busy], with [progress] only when it is that request's;
/// keyed by request id so an opened panel stays open across updates.
Widget liveTrace(Busy busy, LiveProgress? progress) => LiveTrace(
  key: ValueKey('live-${busy.rid}'),
  phase: busy.phase,
  steps: progress?.rid == busy.rid ? progress!.steps : const [],
);
