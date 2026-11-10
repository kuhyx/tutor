/// Dates as numbers (no month or weekday words) and the due marks: overdue
/// = red clock, today = filled dot.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

String _two(int n) => n.toString().padLeft(2, '0');

/// `MM/dd` (`11/09`).
String dateNum(DateTime d) => '${_two(d.month)}/${_two(d.day)}';

/// `yyyy-MM-dd`.
String isoDate(DateTime d) => '${d.year}-${_two(d.month)}-${_two(d.day)}';

/// `HH:mm`.
String clockNum(DateTime d) => '${_two(d.hour)}:${_two(d.minute)}';

/// Minutes as digits: `M` under an hour, else `H:MM` (`1:05`).
String minutesNum(int minutes) =>
    minutes < 60 ? '$minutes' : '${minutes ~/ 60}:${_two(minutes % 60)}';

/// Where a day sits relative to today.
enum DueKind {
  /// Before today, still open.
  overdue,

  /// Today.
  today,

  /// Later (or done): no mark.
  later,
}

/// The [DueKind] of [day] against [now] (local calendar days).
DueKind dueKindOf(DateTime day, DateTime now) {
  final a = DateTime(day.year, day.month, day.day);
  final b = DateTime(now.year, now.month, now.day);
  if (a.isBefore(b)) return DueKind.overdue;
  return a == b ? DueKind.today : DueKind.later;
}

/// The mark of a [DueKind]: red clock, filled dot, or nothing.
class DueMark extends StatelessWidget {
  /// Creates the mark.
  const new(this.kind, {super.key});

  /// Which mark.
  final DueKind kind;

  @override
  Widget build(BuildContext context) => switch (kind) {
    DueKind.overdue => Icon(
      Icons.schedule,
      size: AppTextSize.label,
      color: Theme.of(context).colorScheme.error,
    ),
    DueKind.today => Container(
      width: AppSpacing.sm,
      height: AppSpacing.sm,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.primary,
        shape: BoxShape.circle,
      ),
    ),
    DueKind.later => const SizedBox.shrink(),
  };
}
