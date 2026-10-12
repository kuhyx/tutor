/// One single-series chart over days, as `static/progress.js` draws it:
/// bars (with the daily cap as a dashed reference line) or a line with
/// dots; today is the last point and is emphasised; at most ~8 date labels.
library;

import 'dart:math' as math;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// The chart.
class ProgressChart extends StatelessWidget {
  /// Creates the chart.
  const new({
    required this.values,
    required this.labels,
    required this.unit,
    this.cap,
    this.line = false,
    super.key,
  });

  /// One value per day, oldest first.
  final List<int> values;

  /// `YYYY-MM-DD` per value.
  final List<String> labels;

  /// Unit for the summary.
  final String unit;

  /// Reference line (daily target).
  final int? cap;

  /// Line instead of bars.
  final bool line;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Semantics(
      label:
          '$unit per day, ${values.length} days, '
          'latest ${values.isEmpty ? 0 : values.last}',
      child: SizedBox(
        height: 200,
        child: CustomPaint(
          size: Size.infinite,
          painter: _ChartPainter(
            values: values,
            labels: labels,
            cap: cap,
            line: line,
            mark: AppPalette.accent,
            grid: scheme.outlineVariant,
            text: scheme.onSurfaceVariant,
          ),
        ),
      ),
    );
  }
}

class _ChartPainter extends CustomPainter {
  new({
    required this.values,
    required this.labels,
    required this.cap,
    required this.line,
    required this.mark,
    required this.grid,
    required this.text,
  });

  final List<int> values;
  final List<String> labels;
  final int? cap;
  final bool line;
  final Color mark;
  final Color grid;
  final Color text;

  static const _l = 36.0;
  static const _r = 8.0;
  static const _t = 12.0;
  static const _b = 24.0;

  void _label(Canvas c, String s, Offset at, {bool right = false}) {
    final tp = TextPainter(
      text: TextSpan(
        text: s,
        style: TextStyle(color: text, fontSize: AppTextSize.caption),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(c, at - Offset(right ? tp.width : tp.width / 2, tp.height / 2));
  }

  @override
  void paint(Canvas canvas, Size size) {
    if (values.isEmpty) return;
    final top = [1, cap ?? 0, ...values].reduce(math.max).toDouble();
    final step = (size.width - _l - _r) / values.length;
    double x(int i) => _l + step * (i + 0.5);
    double y(num v) => _t + (size.height - _t - _b) * (1 - v / top);
    final gridPaint = Paint()
      ..color = grid
      ..strokeWidth = 1;
    for (final v in [0, top / 2, top]) {
      canvas.drawLine(
        Offset(_l, y(v)),
        Offset(size.width - _r, y(v)),
        gridPaint,
      );
      _label(canvas, '${v.round()}', Offset(_l - 6, y(v)), right: true);
    }
    if (cap != null) {
      final dash = Paint()
        ..color = mark.withValues(alpha: 0.6)
        ..strokeWidth = 1.5;
      for (var px = _l; px < size.width - _r; px += 8) {
        canvas.drawLine(Offset(px, y(cap!)), Offset(px + 4, y(cap!)), dash);
      }
    }
    final last = values.length - 1;
    final fill = Paint()..color = mark;
    final dim = Paint()..color = mark.withValues(alpha: 0.7);
    if (line) {
      final path = Path();
      for (final (i, v) in values.indexed) {
        i == 0 ? path.moveTo(x(i), y(v)) : path.lineTo(x(i), y(v));
      }
      canvas.drawPath(
        path,
        Paint()
          ..color = mark
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2,
      );
      for (final (i, v) in values.indexed) {
        canvas.drawCircle(Offset(x(i), y(v)), i == last ? 5 : 3, fill);
      }
    } else {
      final w = math.min(32, step - 2).toDouble();
      for (final (i, v) in values.indexed) {
        if (v == 0) continue;
        canvas.drawRRect(
          RRect.fromRectAndCorners(
            Rect.fromLTRB(x(i) - w / 2, y(v), x(i) + w / 2, y(0)),
            topLeft: const Radius.circular(4),
            topRight: const Radius.circular(4),
          ),
          i == last ? fill : dim,
        );
      }
    }
    final every = (values.length / 8).ceil();
    for (var i = 0; i <= last; i++) {
      if (i % every != 0 && i != last) continue;
      final day = labels[i];
      _label(
        canvas,
        i == last ? 'today' : (day.length > 5 ? day.substring(5) : day),
        Offset(x(i), size.height - _b / 2),
      );
    }
  }

  @override
  bool shouldRepaint(_ChartPainter old) =>
      old.values != values || old.cap != cap || old.mark != mark;
}
