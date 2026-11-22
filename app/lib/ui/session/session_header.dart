/// The Session's header: the day's totals and this card's minutes, plus the
/// paused / stalled / stopped marks; in the top bar on a wide desktop
/// window, else a row above the chat. With the phone keyboard open nothing
/// shows (the typing room is taken from it).
/// Text-free: glyph + number; the old sentences are the spoken labels.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/codes.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/session/today_header.dart';
import 'package:tutor/ui/code_glyphs.dart';
import 'package:tutor/ui/session/leetcode_stats.dart';
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
    this.inBar = false,
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

  /// Nothing shows (the phone keyboard is open).
  final bool compact;

  /// It sits in the top bar (wide desktop): no padding of its own.
  final bool inBar;

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
    final lc = meta.leetcode;
    final marks = [
      if (clock.pauseKind case final why?
          when !(why == PauseReason.stalled && live && clock.stalledAt(nowMs)))
        SpokenLabel(
          semanticLabel: 'Clock paused: ${clock.pausedReason}',
          child: Icon(pauseIcon(why), color: AppPalette.warning),
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
    if (compact) return const SizedBox.shrink();
    return Container(
      alignment: inBar ? null : AlignmentDirectional.centerStart,
      padding: inBar
          ? EdgeInsets.zero
          : const EdgeInsets.fromLTRB(
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
          // A theory lesson shows LeetCode's numbers instead of the tutor's.
          if (lc != null)
            LeetcodeStats(meta: lc)
          else ...[
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

/// The header for the top bar (wide desktop) of [meta]; null before the
/// session loads. [now] decides "stalled" (null: the wall clock).
SessionHeader? barStats(
  SessionMeta? meta,
  Today? today,
  DateTime Function()? now,
) => meta == null
    ? null
    : SessionHeader(
        meta: meta,
        today: today,
        nowMs: (now ?? DateTime.now)().millisecondsSinceEpoch,
        live: !meta.stopped,
        inBar: true,
      );
