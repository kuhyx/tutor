import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/plan/today_plan.dart';
import 'package:tutor/storage/kv_store.dart';

Map<String, dynamic> _step(String kind) => {
  'id': 's1',
  'title': 'T',
  'kind': kind,
};

Map<String, dynamic> _plan(String date, List<Map<String, dynamic>> steps) => {
  'date': date,
  'steps': steps,
};

void main() {
  test('a step of an unknown kind is a FormatException', () {
    expect(() => PlanStep.fromJson(_step('teleport')), throwsFormatException);
    expect(PlanStep.fromJson(_step('sql_drill')).kind, StepKind.sqlDrill);
  });

  group('cachedPlan', () {
    late MemoryKv kv;
    setUp(() => kv = MemoryKv());

    test('nothing cached is null', () async {
      expect(await cachedPlan(kv, '2026-11-18'), isNull);
    });

    test('today with steps comes back', () async {
      await cachePlan(kv, _plan('2026-11-18', [_step('note')]));
      final plan = await cachedPlan(kv, '2026-11-18');
      expect(plan!.steps.single.kind, StepKind.note);
    });

    test('another day or no steps is null', () async {
      await cachePlan(kv, _plan('2026-11-17', [_step('note')]));
      expect(await cachedPlan(kv, '2026-11-18'), isNull);
      await cachePlan(kv, _plan('2026-11-18', const []));
      expect(await cachedPlan(kv, '2026-11-18'), isNull);
    });

    test('a corrupt cache is null, not a crash', () async {
      await kv.set('plan.today', jsonEncode([1, 2]));
      expect(await cachedPlan(kv, '2026-11-18'), isNull);
    });
  });
}
