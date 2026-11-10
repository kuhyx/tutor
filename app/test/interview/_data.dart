/// Wire fixtures for the interview tests: the `focus_status` an interview
/// project produces (DOCS-contract-focus.md, "Interview projects").
library;

const Map<String, Object> oldProject = {
  'id': 'hackerrank-prep',
  'name': 'HackerRank prep',
  'start': '2026-11-02',
  'end': '2026-11-05',
  'days_left': 4,
  'replaces': ['leetcode', 'reading'],
  'daily_minutes': 120,
  'unlock_minutes': 30,
  'subjects': ['automation'],
  'site_patterns': ['hackerrank.com'],
};

/// One milestone row.
Map<String, Object> ms(String id, String due, String state) => {
  'id': id,
  'due': due,
  'state': state,
};

/// An interview project; [milestones] default to one of each kind.
Map<String, Object?> interviewProject({
  List<Map<String, Object>>? milestones,
  int minutes = 42,
  int daily = 30,
  bool missed = false,
}) => {
  ...oldProject,
  'id': 'acme-interview',
  'name': 'Acme interview',
  'end': '2026-11-20',
  'days_left': 10,
  'daily_minutes': daily,
  'minutes': minutes,
  'kind': 'interview',
  'test_at': '2026-11-20T10:00:00',
  'invite_url': 'https://app.codility.com/c/acme',
  'trips': [
    {'start': '2026-11-14', 'end': '2026-11-15'},
  ],
  'weekend_answers': {'2026-11-14': true},
  'missed': missed,
  'milestones':
      milestones ??
      [
        ms('rules', '2026-11-10T23:59:00', 'pending'),
        ms('trip_ask:2026-11-14', '2026-11-12T23:59:00', 'pending'),
        ms('phone:2026-11-14', '2026-11-13T12:00:00', 'pending'),
        ms('mock', '2026-11-18T23:59:00', 'pending'),
        ms('slot', '2026-11-19T12:00:00', 'pending'),
      ],
};

/// A `focus_status` result around [project] (the active one).
Map<String, Object?> statusOf(Map<String, Object?> project) => {
  'day': '2026-11-10',
  'active': project,
  'projects': [project],
  'gates': [
    {'id': 'leetcode', 'label': 'LeetCode', 'replaceable': true},
    {'id': 'workout', 'label': 'Workout', 'replaceable': false},
  ],
  'subjects': [
    {'id': 'automation', 'title': 'Automation'},
  ],
};
