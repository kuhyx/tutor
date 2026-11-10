/// The interview part of a `focus_status` project row (DOCS-contract-focus.md,
/// "Interview projects"): milestones with their state, trips, weekend
/// answers. An old server sends none of it, so every field here is optional
/// on the wire and a project without them is a plain focus project.
library;

import 'package:tutor/model/json.dart';

/// Where a milestone stands; red is [missed] or [unknown].
enum MilestoneState {
  /// Before its due time, not done.
  pending('pending'),

  /// Done in time.
  done('done'),

  /// Past due, not done.
  missed('missed'),

  /// Done after the due time: no longer locks.
  lateDone('late_done'),

  /// The check could not run: counts as not done.
  unknown('unknown');

  new(this.wire);

  /// Wire name.
  final String wire;

  /// A word the server does not know yet reads as [unknown]: red, never
  /// silently green.
  static MilestoneState parse(String s) => values.firstWhere(
    (v) => v.wire == s,
    orElse: () => MilestoneState.unknown,
  );

  /// Shown red.
  bool get red => this == missed || this == unknown;

  /// Counts as done.
  bool get ok => this == done || this == lateDone;
}

/// One generated milestone; `due` is a naive local time.
typedef Milestone = ({String id, DateTime due, MilestoneState state});

/// An announced trip, inclusive `YYYY-MM-DD` days.
typedef Trip = ({String start, String end});

/// Everything an interview row adds to a project.
typedef InterviewState = ({
  DateTime? testAt,
  String inviteUrl,
  List<Trip> trips,
  Map<String, bool> weekendAnswers,
  List<Milestone> milestones,
  bool missed,
});

/// The milestone kinds, one icon each.
enum MilestoneGroup {
  /// The rules screenshot.
  rules,

  /// The weekend trip question.
  tripAsk,

  /// Phone prep before a trip.
  phone,

  /// The timed mock.
  mock,

  /// The test slot.
  slot,
}

/// The group of milestone [id] (`phone:2026-11-14` is [MilestoneGroup.phone]);
/// null for a kind this app does not know.
MilestoneGroup? groupOf(String id) => switch (id.split(':').first) {
  'rules' => MilestoneGroup.rules,
  'trip_ask' => MilestoneGroup.tripAsk,
  'phone' => MilestoneGroup.phone,
  'mock' => MilestoneGroup.mock,
  'slot' => MilestoneGroup.slot,
  _ => null,
};

/// The part of [id] after the first colon (a Saturday or a trip start).
String? argOf(String id) {
  final i = id.indexOf(':');
  return i < 0 ? null : id.substring(i + 1);
}

/// What an icon shows.
enum Light {
  /// Pending, or nothing to show yet.
  grey,

  /// Every milestone of the group is done.
  green,

  /// Some milestone is missed or unknown.
  red,
}

/// A group's light: red if any member is red, green when all are done.
Light groupLight(Iterable<Milestone> group) {
  if (group.any((m) => m.state.red)) return Light.red;
  if (group.isNotEmpty && group.every((m) => m.state.ok)) return Light.green;
  return Light.grey;
}

/// The milestone a tap acts on: the first red one, else the earliest-due
/// pending one; null when all are done.
Milestone? actionable(List<Milestone> group) {
  final todo = [
    for (final m in group)
      if (!m.state.ok) m,
  ]..sort((a, b) => a.due.compareTo(b.due));
  for (final m in todo) {
    if (m.state.red) return m;
  }
  return todo.isEmpty ? null : todo.first;
}

Milestone _milestone(Object? v) {
  final j = asJson(v);
  return (
    id: str(j, 'id'),
    due: DateTime.parse(str(j, 'due')),
    state: MilestoneState.parse(str(j, 'state')),
  );
}

List<Trip> _trips(Json j) => listOf(j, 'trips', (v) {
  final t = asJson(v);
  return (start: str(t, 'start'), end: str(t, 'end'));
});

Map<String, bool> _answers(Json j) {
  final raw = objOr(j, 'weekend_answers') ?? const <String, dynamic>{};
  return {for (final e in raw.entries) e.key: e.value == true};
}

/// The interview part of project row [j]; null for a plain focus project.
InterviewState? parseInterview(Json j) {
  if (strOr(j, 'kind') != 'interview') return null;
  final at = strOr(j, 'test_at');
  return (
    testAt: at == null ? null : DateTime.parse(at),
    inviteUrl: strOr(j, 'invite_url') ?? '',
    trips: _trips(j),
    weekendAnswers: _answers(j),
    milestones: listOf(j, 'milestones', _milestone),
    missed: flag(j, 'missed'),
  );
}

/// [state] redrawn from the block a `focus_evidence` / `focus_trip` /
/// `focus_weekend` result carries (`milestones`, `missed`, `trips`,
/// `weekend_answers`); the test time and invite url are not in it.
InterviewState applyBlock(InterviewState state, Json block) => (
  testAt: state.testAt,
  inviteUrl: state.inviteUrl,
  trips: _trips(block),
  weekendAnswers: _answers(block),
  milestones: listOf(block, 'milestones', _milestone),
  missed: flag(block, 'missed'),
);
