import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/progress/progress.dart';

SubjectData _subject(String title, List<Module> modules) => SubjectData(
  id: title.toLowerCase(),
  meta: SubjectMeta(
    title: title,
    goal: '',
    status: SubjectStatus.active,
    created: 1,
    planRev: 1,
    rev: 1,
    origin: 'seed',
  ),
  plan: Plan(rev: 1, status: 'approved', modules: modules),
);

void main() {
  test('timeline: sorted, cumulative over all days, last N', () {
    final days = {
      '2026-10-12': const DayStats(minutes: 30, taught: 2, reviews: 5),
      '2026-10-10': const DayStats(minutes: 10, taught: 1, reviews: 0),
      '2026-10-11': const DayStats(minutes: 0, taught: 0, reviews: 3),
    };
    final all = timeline(days);
    expect(all.map((d) => d.day).first, '2026-10-10');
    expect(all.last.taughtTotal, 3);
    final last2 = timeline(days, maxDays: 2);
    expect(last2.map((d) => d.taughtTotal), [1, 3]);
    expect(last2.last.minutes, 30);
    expect(last2.last.reviews, 5);
    expect(last2.last.taught, 2);
  });

  test('module progress and mastered counts', () {
    final b = _subject('B', const [
      Module(id: 'x', title: 'X', status: ModuleStatus.mastered),
      Module(id: 'y', title: 'Y', recall: 0.5),
    ]);
    final a = _subject('A', const [Module(id: 'z', title: 'Z')]);
    final rows = moduleProgress([b, a]);
    expect(rows.map((r) => '${r.subject}/${r.module.id}'), [
      'A/z',
      'B/x',
      'B/y',
    ]);
    expect(masteredOf(b), (1, 2));
    expect(masteredOf(SubjectData(id: 'n', meta: a.meta)), (0, 0));
  });
}
