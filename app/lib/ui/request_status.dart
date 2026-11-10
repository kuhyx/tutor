/// A request's status as a cue (textgate): the PC-offline banner and the
/// status line under a request's button.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/relay_cue.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// A cloud-off cue while the PC is silent (replies wait; reviews work).
class PcOfflineBanner extends StatelessWidget {
  /// Creates the banner.
  const new(this.presence, {super.key});

  /// PC presence.
  final ValueNotifier<PcPresence> presence;

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<PcPresence>(
    valueListenable: presence,
    builder: (context, value, _) => value != PcPresence.offline
        ? const SizedBox.shrink()
        : const Padding(
            padding: EdgeInsets.symmetric(vertical: AppSpacing.sm),
            child: CueChip(kind: CueKind.offline, semanticLabel: pcOfflineText),
          ),
  );
}

/// The status of a [RequestRunner]'s last request as a cue: a spinner or
/// glyph while waiting, a red shaking error chip on failure (a block shows
/// its call-to-action glyph), a retry button, nothing once done. The
/// sentences are spoken only.
class RequestStatusLine extends StatelessWidget {
  /// Creates the line.
  const new(
    this.runner, {
    this.queuedText,
    this.queuedSpoken,
    this.stalledText,
    super.key,
  });

  /// The runner.
  final RequestRunner runner;

  /// Spoken instead of the waiting/phase line once the runner is stalled
  /// (no result and no progress for minutes); null keeps the plain line.
  final String? stalledText;

  /// A ledger-approved sentence painted next to the waiting glyph while
  /// queued (focus: "Saved, sending later"); null = glyph only.
  final String? queuedText;

  /// Spoken instead of the default "waiting for the PC" while queued.
  final String? queuedSpoken;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: Listenable.merge([runner.status, runner.stalled]),
    builder: (context, _) {
      final s = runner.status.value;
      final lost = runner.stalled.value ? stalledText : null;
      final cue = relayCue(s, stalled: lost);
      if (cue == null) return const SizedBox.shrink();
      final queued = s is RelayQueued && lost == null ? queuedText : null;
      final error = cue.kind == CueKind.error;
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
        child: Row(
          children: [
            // Expanded: the approved queued words wrap at large fonts.
            Expanded(
              child: Align(
                alignment: AlignmentDirectional.centerStart,
                child: CueChip(
                  kind: cue.kind,
                  icon: cue.icon,
                  semanticLabel: s is RelayQueued && queuedSpoken != null
                      ? queuedSpoken!
                      : cue.semanticLabel,
                  trailing: [
                    if (queued != null) ...[
                      const SizedBox(width: AppSpacing.sm),
                      Flexible(child: Text(queued)),
                    ],
                  ],
                ),
              ),
            ),
            if (runner.canRetry)
              GlyphButton(
                icon: Icons.refresh,
                semanticLabel: 'Retry',
                onPressed: runner.retry,
              ),
            if (error && lost == null)
              GlyphButton(
                icon: Icons.close,
                semanticLabel: 'Dismiss',
                onPressed: runner.clear,
              ),
          ],
        ),
      );
    },
  );
}

/// Rebuilds [builder] on every change to [runner]'s status or stall, so a
/// box or button can lock while a request is in flight.
class RunnerBuilder extends StatelessWidget {
  /// Creates the builder.
  const new(this.runner, this.builder, {super.key});

  /// The runner watched.
  final RequestRunner runner;

  /// Builds the child from the runner's current state.
  final WidgetBuilder builder;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: runner.changes,
    builder: (c, _) => builder(c),
  );
}
