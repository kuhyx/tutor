/// The tutor's thinking and research (DOCS-contract §6 `trace` / `progress`):
/// a thinking-head toggle on each tutor bubble, and, while a turn is
/// in flight, the busy line with the research steps appearing as they
/// happen (the reasoning itself stays folded until opened).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/model/trace.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/ui/relay_cue.dart';
import 'package:tutor/ui/session/thinking_glyph.dart';
import 'package:tutor/widgets/spoken_label.dart';

export 'package:tutor/ui/session/thinking_glyph.dart';

/// A collapsible trace; folded by default. The live turn's panel (the
/// finished tutor bubble uses [ThinkingGlyph] and [ThinkingBody]).
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
          ThinkingGlyph(
            steps: steps,
            open: _open,
            onToggle: () => setState(() => _open = !_open),
            leading: Icon(
              _open ? Icons.expand_less : Icons.expand_more,
              size: 18,
              color: muted,
            ),
          ),
          ThinkingBody(shown),
        ],
      ),
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
        // Busy: a spinner beside the phase glyph; the sentence is spoken.
        SpokenLabel(
          semanticLabel: researching ? 'Researching...' : phaseText(phase),
          liveRegion: true,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox.square(
                dimension: AppSpacing.md,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
              const SizedBox(width: AppSpacing.sm),
              Icon(researching ? Icons.search : phaseIcon(phase)),
            ],
          ),
        ),
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
