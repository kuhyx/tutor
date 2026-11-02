/// Today's plan: a short linear list of steps the server hands out
/// (`plan_today`), so tomorrow's plan needs no new APK. Wire shape in
/// tutor/relay/plan.py; RTDB drops empty strings and lists, so `target` and
/// `steps` may be absent.
library;

import 'dart:convert';

import 'package:tutor/model/json.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/storage/kv_store.dart';

/// What a step opens.
enum StepKind {
  /// The problem coach on `target` (a LeetCode slug).
  coach,

  /// The SQL lesson of topic `target`.
  sqlLesson('sql_lesson'),

  /// SQL practice.
  sqlDrill('sql_drill'),

  /// Due cards of subject `target`.
  cards,

  /// The mock test; target `review` opens its result.
  mock,

  /// Nothing to open: read and tick.
  note;

  new([this._wire]);
  final String? _wire;

  /// The wire name.
  String get wire => _wire ?? name;

  /// Parses a wire name; null for one this build does not know.
  static StepKind? tryParse(String s) {
    for (final k in values) {
      if (k.wire == s) return k;
    }
    return null;
  }
}

/// One step.
class PlanStep {
  /// Creates a step.
  const new({
    required this.id,
    required this.title,
    required this.what,
    required this.kind,
    required this.target,
    required this.done,
  });

  /// Parses one step; [FormatException] on a bad shape.
  factory fromJson(Json j) => PlanStep(
    id: str(j, 'id'),
    title: str(j, 'title'),
    what: strOr(j, 'what') ?? '',
    kind:
        StepKind.tryParse(str(j, 'kind')) ??
        (throw FormatException('unknown step kind "${j['kind']}"')),
    target: strOr(j, 'target') ?? '',
    done: j['done'] == true,
  );

  /// Stable id within the day.
  final String id;

  /// Heading.
  final String title;

  /// One or two sentences: what to do.
  final String what;

  /// What Start opens.
  final StepKind kind;

  /// Slug, topic, subject id or minutes, by [kind].
  final String target;

  /// Ticked.
  final bool done;
}

/// The day's plan.
class TodayPlan {
  /// Creates a plan.
  const new({required this.date, required this.steps});

  /// Parses `plan_today`'s data; steps of an unknown kind are skipped so a
  /// newer server cannot break an older app.
  factory fromJson(Json j) => TodayPlan(
    date: str(j, 'date'),
    steps: [
      for (final s in (j['steps'] as List<dynamic>?) ?? <dynamic>[])
        if (s is Map<String, dynamic> &&
            StepKind.tryParse('${s['kind']}') != null)
          PlanStep.fromJson(s),
    ],
  );

  /// `YYYY-MM-DD` (the PC's local day).
  final String date;

  /// In order.
  final List<PlanStep> steps;

  /// The first step not done, or null when all are.
  PlanStep? get current {
    for (final s in steps) {
      if (!s.done) return s;
    }
    return null;
  }

  /// Steps done.
  int get doneCount => steps.where((s) => s.done).length;
}

/// `plan_today`.
RequestBody planToday() => const RequestBody.raw(RequestKind.planToday, {});

/// `plan_step_done`.
RequestBody planStepDone(String id) =>
    RequestBody.raw(RequestKind.planStepDone, {'id': id});

const _cacheKey = 'plan.today';

/// Remembers [data] (a `plan_today` result) for a fast, offline next start.
Future<void> cachePlan(KvStore kv, Json data) =>
    kv.set(_cacheKey, jsonEncode(data));

/// The remembered plan when it is for [today] and has steps, else null.
Future<TodayPlan?> cachedPlan(KvStore kv, String today) async {
  final raw = await kv.get(_cacheKey);
  if (raw == null) return null;
  try {
    final plan = TodayPlan.fromJson(asJson(jsonDecode(raw)));
    return plan.date == today && plan.steps.isNotEmpty ? plan : null;
  } on FormatException {
    return null;
  }
}

/// The local date as the server writes it.
String localDay([DateTime? now]) {
  final d = now ?? DateTime.now();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${d.year}-${two(d.month)}-${two(d.day)}';
}
