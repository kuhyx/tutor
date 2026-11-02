import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/focus/focus_models.dart';

Map<String, Object?> _project(Map<String, Object?> extra) => {
  'id': 'hr',
  'name': 'HR',
  'start': '2026-11-02',
  'end': '2026-11-05',
  'days_left': 4,
  'replaces': ['leetcode'],
  'daily_minutes': 120,
  'unlock_minutes': 30,
  'subjects': <String>[],
  'site_patterns': ['hackerrank.com'],
  ...extra,
};

FocusStatus _parse(Map<String, Object?> project) => parseStatus({
  'day': '2026-11-02',
  'active': project,
  'projects': [project],
  'gates': <Object?>[],
  'subjects': <Object?>[],
});

void main() {
  test('the work URL is parsed', () {
    final got = _parse(_project({'work_url': 'https://a.com/x'}));
    expect(got.active!.workUrl, 'https://a.com/x');
    expect(got.projects.single.workUrl, 'https://a.com/x');
  });

  test('a PC that sends no work URL reads as empty', () {
    expect(_parse(_project({})).active!.workUrl, '');
  });
}
