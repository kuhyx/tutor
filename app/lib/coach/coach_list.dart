/// The coach's picker data: languages, a LeetCode URL or slug as typed, and
/// the `lc_list` result (due re-tests, recent problems, the live session).
library;

import 'package:tutor/model/json.dart';

/// Language ids (LeetCode langSlugs) and their names, in picker order.
const coachLangs = <String, String>{
  'mysql': 'MySQL',
  'postgresql': 'PostgreSQL',
  'python3': 'Python 3',
  'javascript': 'JavaScript',
  'typescript': 'TypeScript',
};

/// The language when none was chosen.
const defaultCoachLang = 'python3';

/// Whether `lang` is a SQL dialect (tables, not text, in results).
bool isSqlLang(String lang) => lang == 'mysql' || lang == 'postgresql';

final _slug = RegExp(r'^[a-z0-9]+(-[a-z0-9]+)*$');

/// The problem slug in `input` (a slug, or a `leetcode.com/problems/slug`
/// URL with any tail); null when it is neither.
String? slugFromInput(String input) {
  final text = input.trim().toLowerCase();
  if (_slug.hasMatch(text)) return text;
  final uri = Uri.tryParse(text.contains('://') ? text : 'https://$text');
  if (uri == null || !uri.host.contains('leetcode.')) return null;
  final parts = uri.pathSegments;
  final at = parts.indexOf('problems');
  final slug = at >= 0 && at + 1 < parts.length ? parts[at + 1] : '';
  return _slug.hasMatch(slug) ? slug : null;
}

/// A problem in a list; `note` is the due stage (`+3 d`) of a re-test.
typedef ProblemRef = ({
  String slug,
  String title,
  String difficulty,
  String? note,
});

/// `lc_list`: `lcId` is the live session id, if one is open.
typedef CoachList = ({
  String? lcId,
  List<ProblemRef> due,
  List<ProblemRef> recent,
});

/// A list that RTDB may have stored as an index-keyed map; absent = empty.
List<Object?> items(Object? v, String what) {
  if (v == null) return const [];
  if (v is List) return v;
  if (v is Map) {
    final keys = v.keys.map((k) => int.tryParse('$k')).toList();
    if (keys.contains(null)) {
      throw FormatException('"$what": expected array, got object');
    }
    final sorted = v.entries.toList()
      ..sort((a, b) => int.parse('${a.key}').compareTo(int.parse('${b.key}')));
    return [for (final e in sorted) e.value];
  }
  throw FormatException('"$what": expected array, got ${v.runtimeType}');
}

ProblemRef _ref(Object? v) {
  final j = asJson(v, 'problem');
  final slug = str(j, 'slug');
  return (
    slug: slug,
    title: strOr(j, 'title') ?? slug,
    difficulty: strOr(j, 'difficulty') ?? '',
    note: strOr(j, 'note'),
  );
}

/// Parses an `lc_list` result.
CoachList parseCoachList(Json j) => (
  lcId: strOr(j, 'lc_id'),
  due: [for (final e in items(j['due'], 'due')) _ref(e)],
  recent: [for (final e in items(j['recent'], 'recent')) _ref(e)],
);
