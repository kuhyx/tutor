import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// Timer minutes no beat backs: a muted timer-off glyph and the count.
///
/// Text-free (textgate): the old line "{n} min unbacked (not counted)" is
/// only the spoken label, which the F11 driver still matches.
class UnbackedMark extends StatelessWidget {
  /// Creates the mark for [minutes] (> 0) unbacked minutes.
  const new(this.minutes, {super.key});

  /// The unbacked minutes.
  final int minutes;

  @override
  Widget build(BuildContext context) {
    final muted = Theme.of(context).colorScheme.outline;
    return SpokenLabel(
      semanticLabel: '$minutes min unbacked (not counted)',
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.timer_off_outlined, size: AppTextSize.label, color: muted),
          const SizedBox(width: AppSpacing.xs),
          Text(
            '$minutes',
            style: Theme.of(context).textTheme.bodyMedium
                ?.copyWith(color: muted),
          ),
        ],
      ),
    );
  }
}
