/// The Session's header: the day's totals and this card's minutes, plus the
/// paused / stalled / stopped marks. With the phone keyboard open only the
/// marks stay (the lines are what the typing room is taken from).
/// Text-free: glyph + number; the old sentences are the spoken labels.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/session/today_header.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// The header.
class SessionHeader extends StatelessWidget {
  /// Creates the header; [nowMs] decides "stalled".
  const new({
    required this.meta,
    required this.today,
    required this.nowMs,
    required this.live,
    this.compact = false,
    super.key,
  });

  /// The session's meta.
  final SessionMeta meta;

  /// `stats.today` (null until read).
  final Today? today;

  /// Clock (ms since epoch).
  final int nowMs;

  /// The session is live (not stopped).
  final bool live;

  /// Lines hidden, marks only.
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final clock = meta.clock;
    final lines = headerLines(
      today,
      activeSeconds: clock.activeSeconds,
      sessionCredited: meta.creditedMinutes,
    );
    final t = today;
    final marks = [
      if (clock.pausedReason != null)
        SpokenLabel(
          semanticLabel: 'Clock paused: ${clock.pausedReason}',
          child: const Icon(
            Icons.pause_circle_outline,
            color: AppPalette.warning,
          ),
        ),
      if (live && clock.stalledAt(nowMs))
        const SpokenLabel(
          semanticLabel: 'Stalled: no reply for 10 min',
          child: Icon(Icons.hourglass_disabled, color: AppPalette.warning),
        ),
      if (meta.stopped)
        const SpokenLabel(
          semanticLabel: 'Stopped',
          child: Icon(Icons.stop_circle_outlined),
        ),
    ];
    if (compact && marks.isEmpty) return const SizedBox.shrink();
    return Container(
      alignment: AlignmentDirectional.centerStart,
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.md,
        AppSpacing.sm,
        AppSpacing.md,
        0,
      ),
      child: Wrap(
        spacing: AppSpacing.md,
        runSpacing: AppSpacing.xs,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          if (!compact) ...[
            // The day's totals lead; this card's minutes are secondary.
            SpokenLabel(
              semanticLabel: lines.$1,
              child: Wrap(
                spacing: AppSpacing.md,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  if (t?.activeMinutes != null)
                    GlyphStat(
                      Icons.timer_outlined,
                      '${t!.activeMinutes}',
                      size: AppTextSize.subtitle,
                    ),
                  if (t != null)
                    GlyphStat(
                      Icons.bolt,
                      '${t.creditedMinutes}/${t.target}',
                      size: AppTextSize.subtitle,
                    ),
                  if (t != null && bankNote(t) != null) ...[
                    GlyphStat(Icons.savings_outlined, '${t.banked ?? 0}'),
                    GlyphStat(Icons.event_available, '${t.prepaid ?? 0}'),
                  ],
                ],
              ),
            ),
            SpokenLabel(
              semanticLabel: lines.$2,
              child: Wrap(
                spacing: AppSpacing.sm,
                children: [
                  GlyphStat(
                    Icons.style_outlined,
                    '${(clock.activeSeconds / 60).floor()}',
                    color: scheme.onSurfaceVariant,
                  ),
                  GlyphStat(
                    Icons.bolt,
                    '${meta.creditedMinutes}',
                    color: scheme.onSurfaceVariant,
                  ),
                ],
              ),
            ),
          ],
          ...marks,
        ],
      ),
    );
  }
}
