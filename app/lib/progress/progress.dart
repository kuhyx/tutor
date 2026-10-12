/// Progress (curriculum §7/§8): the `stats.days` timeline and per-module
/// recall, as `static/progress.js` shows them (minutes per day against the
/// daily target; cards taught, cumulative).
library;

import 'package:tutor/home/catalog.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/stats.dart';

/// One day on the timeline.
class DayPoint {
  /// Creates the point.
  const new({
    required this.day,
    required this.minutes,
    required this.taught,
    required this.reviews,
    required this.taughtTotal,
  });

  /// `YYYY-MM-DD`.
  final String day;

  /// Credited minutes that day.
  final int minutes;

  /// Cards taught that day.
  final int taught;

  /// Reviews that day.
  final int reviews;

  /// Cards taught up to and including that day.
  final int taughtTotal;
}

/// The last [maxDays] days of [days], oldest first, with running totals
/// counted over ALL days (so the cumulative line does not restart).
List<DayPoint> timeline(Map<String, DayStats> days, {int maxDays = 60}) {
  final keys = days.keys.toList()..sort();
  var total = 0;
  final points = <DayPoint>[];
  for (final k in keys) {
    final d = days[k]!;
    total += d.taught;
    points.add(
      DayPoint(
        day: k,
        minutes: d.minutes,
        taught: d.taught,
        reviews: d.reviews,
        taughtTotal: total,
      ),
    );
  }
  return points.length <= maxDays
      ? points
      : points.sublist(points.length - maxDays);
}

/// One module's row.
class ModuleProgress {
  /// Creates the row.
  const new(this.subject, this.module);

  /// Subject title.
  final String subject;

  /// The module (status, recall, cards).
  final Module module;
}

/// Every module of every subject with a plan, in teaching order, subjects
/// by title.
List<ModuleProgress> moduleProgress(Iterable<SubjectData> subjects) {
  final sorted = subjects.toList()
    ..sort((a, b) => a.meta.title.compareTo(b.meta.title));
  return [
    for (final s in sorted)
      for (final m in s.plan?.modules ?? const <Module>[])
        ModuleProgress(s.meta.title, m),
  ];
}

/// `mastered/total` modules of [s] (Home's per-subject progress).
(int, int) masteredOf(SubjectData s) {
  final modules = s.plan?.modules ?? const <Module>[];
  return (
    modules.where((m) => m.status == ModuleStatus.mastered).length,
    modules.length,
  );
}
