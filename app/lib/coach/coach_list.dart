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

/// A past or live session, resumed by `lcId`.
typedef Recent = ({
  String lcId,
  String slug,
  String title,
  String phase,
  int updatedMs,
});

/// A cold re-test that is due (never submitted on LeetCode).
typedef Due = ({String slug, String title, int dueMs});

/// A named group of problem slugs.
typedef Cluster = ({String name, List<String> problems});

/// `lc_list`.
typedef CoachList = ({
  List<Recent> recent,
  List<Cluster> clusters,
  List<Due> due,
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

Recent _recent(Object? v) {
  final j = asJson(v, 'recent');
  final slug = str(j, 'slug');
  return (
    lcId: str(j, 'lc_id'),
    slug: slug,
    title: strOr(j, 'title') ?? slug,
    phase: strOr(j, 'phase') ?? 'work',
    updatedMs: intOr(j, 'updated_ms') ?? 0,
  );
}

Due _due(Object? v) {
  final j = asJson(v, 'due');
  final slug = str(j, 'slug');
  return (
    slug: slug,
    title: strOr(j, 'title') ?? slug,
    dueMs: intOr(j, 'due_ms') ?? 0,
  );
}

Cluster _cluster(Object? v) {
  final j = asJson(v, 'clusters');
  return (
    name: str(j, 'name'),
    problems: [for (final p in items(j['problems'], 'problems')) '$p'],
  );
}

/// Parses an `lc_list` result.
CoachList parseCoachList(Json j) => (
  recent: [for (final e in items(j['recent'], 'recent')) _recent(e)],
  clusters: [for (final e in items(j['clusters'], 'clusters')) _cluster(e)],
  due: [for (final e in items(j['due'], 'due')) _due(e)],
);
