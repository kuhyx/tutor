/// The live session as a LeetCode theory lesson (`?lc=1` in the screenshot
/// build): `meta.leetcode` as the server writes it.
library;

import 'package:tutor/sync/json_tree.dart';

import 'fixture_sessions.dart' show fixtureLiveSid;

/// The `leetcode` map for [mode]: `unknown` (the four counts missing: could
/// not check), `full` (the day's minutes are capped), else a normal one.
Map<String, Object?> fixtureLeetcode(String mode) => switch (mode) {
  'unknown' => {'unit': 'prefix-sums', 'taught': 3, 'total': 9, 'full': false},
  'full' => {
    'unit': 'prefix-sums',
    'taught': 3,
    'total': 9,
    'full': true,
    'into': 12,
    'per_credit': 12,
    'credits': 2,
    'needed': 5,
  },
  _ => {
    'unit': 'prefix-sums',
    'taught': 3,
    'total': 9,
    'full': false,
    'into': 7,
    'per_credit': 12,
    'credits': 1,
    'needed': 6,
  },
};

/// [root] (the tree under `tutor/v1-e2e`) with the live session's meta
/// carrying [leetcode].
Object? fixtureWithLeetcode(Object? root, Map<String, Object?> leetcode) {
  const path = 'tutor/v1-e2e/sessions/$fixtureLiveSid/meta';
  final meta = getAt(root, path)! as Map<String, dynamic>;
  return setAt(root, path, {...meta, 'leetcode': leetcode});
}
