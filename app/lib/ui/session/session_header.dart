/// The Session's header: the day's totals and this card's minutes, plus the
/// paused / stalled / stopped pills. With the phone keyboard open only the
/// pills stay (the lines are what the typing room is taken from).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/session/today_header.dart';
import 'package:tutor/ui/common.dart';

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

  /// Lines hidden, pills only.
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final clock = meta.clock;
    final lines = headerLines(
      today,
      activeSeconds: clock.activeSeconds,
      sessionCredited: meta.creditedMinutes,
    );
    final pills = [
      if (clock.pausedReason != null)
        Pill('Clock paused: ${clock.pausedReason}', warn: true),
      if (live && clock.stalledAt(nowMs))
        const Pill('Stalled: no reply for 10 min', warn: true),
      if (meta.stopped) const Pill('Stopped'),
    ];
    if (compact && pills.isEmpty) return const SizedBox.shrink();
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
            Text(lines.$1, style: text.titleMedium),
            Text(
              lines.$2,
              style: text.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
          ...pills,
        ],
      ),
    );
  }
}
