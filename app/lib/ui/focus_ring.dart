import 'dart:math' as math;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// A progress ring: [minutes] over [goal] inside, [caption] beneath.
class FocusRing extends StatelessWidget {
  /// Creates the ring.
  const new({
    required this.minutes,
    required this.goal,
    this.caption,
    this.banked,
    super.key,
  });

  /// Minutes counted today.
  final int minutes;

  /// Minutes wanted today.
  final int goal;

  /// Second line inside the ring.
  final String? caption;

  /// Overtime banked for tomorrow, e.g. `(+1 banked)`; null when none.
  final String? banked;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final scheme = Theme.of(context).colorScheme;
    final done = goal > 0 && minutes >= goal;
    return Semantics(
      label: '$minutes/$goal',
      child: AspectRatio(
        aspectRatio: 1,
        child: CustomPaint(
          painter: _RingPainter(
            value: goal == 0 ? 0 : (minutes / goal).clamp(0, 1),
            track: scheme.surfaceContainerHighest,
            fill: done ? AppPalette.success : AppPalette.accent,
          ),
          child: Center(
            child: ExcludeSemantics(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(minutes.toString(), style: text.displayMedium),
                  SizedBox(
                    width: 64,
                    child: Divider(color: scheme.onSurface, thickness: 2),
                  ),
                  Text(goal.toString(), style: text.titleLarge),
                  if (banked != null) Text(banked!, style: text.bodyMedium),
                  if (caption != null) Text(caption!, style: text.bodyMedium),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  const new({required this.value, required this.track, required this.fill});

  final double value;
  final Color track;
  final Color fill;

  @override
  void paint(Canvas canvas, Size size) {
    const width = 16.0;
    final rect = (Offset.zero & size).deflate(width / 2);
    Paint stroke(Color c) => Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = width
      ..strokeCap = StrokeCap.round
      ..color = c;
    canvas
      ..drawArc(rect, 0, 2 * math.pi, false, stroke(track))
      ..drawArc(rect, -math.pi / 2, 2 * math.pi * value, false, stroke(fill));
  }

  @override
  bool shouldRepaint(_RingPainter old) =>
      old.value != value || old.track != track || old.fill != fill;
}
