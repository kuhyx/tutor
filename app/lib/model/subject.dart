/// `subjects/{subj}/meta` (curriculum §1, worker-written).
library;

import 'package:tutor/model/json.dart';

/// Subject lifecycle.
enum SubjectStatus {
  /// The model is drafting the plan.
  drafting,

  /// Plan awaits approval.
  draft,

  /// Being taught.
  active,

  /// Every module mastered.
  completed,

  /// Nothing new; reviews only.
  reviewOnly('review_only');

  new([this._wire]);

  final String? _wire;

  /// Name on the wire.
  String get wire => _wire ?? name;

  /// Parses a wire name.
  static SubjectStatus parse(String s) => byWire(values, s, (v) => v.wire);
}

/// `subjects/{subj}/meta`.
class SubjectMeta {
  /// Creates the record.
  const new({
    required this.title,
    required this.goal,
    required this.status,
    required this.created,
    required this.planRev,
    required this.rev,
    required this.origin,
  });

  /// Parses `meta`.
  factory fromJson(Json j) => SubjectMeta(
    title: str(j, 'title'),
    goal: strOr(j, 'goal') ?? '',
    status: SubjectStatus.parse(str(j, 'status')),
    created: integer(j, 'created'),
    planRev: intOr(j, 'plan_rev') ?? 0,
    rev: integer(j, 'rev'),
    origin: str(j, 'origin'),
  );

  /// Display title.
  final String title;

  /// kuhy's original goal text.
  final String goal;

  /// Lifecycle status.
  final SubjectStatus status;

  /// Creation time (ms).
  final int created;

  /// Current plan revision.
  final int planRev;

  /// Bumps on any change under the subject.
  final int rev;

  /// `seed` (migrated) or `generated`.
  final String origin;

  /// Wire form.
  Json toJson() => compact({
    'title': title,
    'goal': goal.isEmpty ? null : goal,
    'status': status.wire,
    'created': created,
    'plan_rev': planRev,
    'rev': rev,
    'origin': origin,
  });
}
