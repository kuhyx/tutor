// `meta.leetcode`: the LeetCode accounting a theory lesson carries. Absent
// = an ordinary session; a missing count = "could not check", never 0.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/session/leetcode_label.dart';

import '../../tool/fixture/fixture_leetcode.dart';
import '../../tool/fixture/fixture_sessions.dart';

Map<String, dynamic> _raw() {
  final tree = fixtureSessions(0)['sessions']! as Map<String, dynamic>;
  return (tree[fixtureLiveSid]! as Map<String, dynamic>)['meta']!
      as Map<String, dynamic>;
}

SessionMeta _meta(Map<String, Object?>? leetcode) =>
    SessionMeta.fromJson({..._raw(), 'leetcode': ?leetcode});

void main() {
  test('a session without the map is an ordinary one', () {
    expect(_meta(null).leetcode, isNull);
    expect(_meta(null).toJson().containsKey('leetcode'), isFalse);
  });

  test('the full map parses and round-trips', () {
    final m = _meta(fixtureLeetcode('normal'));
    final lc = m.leetcode!;
    expect(
      (lc.unit, lc.taught, lc.total, lc.full),
      ('prefix-sums', 3, 9, false),
    );
    expect((lc.into, lc.perCredit, lc.credits, lc.needed), (7, 12, 1, 6));
    expect(m.toJson()['leetcode'], fixtureLeetcode('normal'));
  });

  test('a missing count is null (could not check), not 0', () {
    final lc = _meta(fixtureLeetcode('unknown')).leetcode!;
    expect(
      (lc.into, lc.perCredit, lc.credits, lc.needed),
      (null, null, null, null),
    );
    expect(lc.toJson().keys, {'unit', 'taught', 'total', 'full'});
  });

  test('a wrong type names the field', () {
    expect(
      () => _meta({...fixtureLeetcode('normal'), 'taught': 'x'}),
      throwsFormatException,
    );
    expect(() => _meta({'taught': 1}), throwsFormatException);
    expect(
      () => SessionMeta.fromJson({..._raw(), 'leetcode': 'x'}),
      throwsFormatException,
    );
  });

  test('spoken lines say the numbers, and "unknown" for a missing one', () {
    final ok = leetcodeLines(_meta(fixtureLeetcode('normal')).leetcode!);
    expect(ok.minutes, 'LeetCode: 7 of 12 min to the next credit');
    expect(ok.credits, 'LeetCode credits today: 1');
    expect(ok.needed, 'LeetCode solves still owed today: 6');
    expect(ok.cards, 'Cards taught in this unit: 3 of 9');
    expect(ok.unit, 'Unit: prefix-sums');
    final full = leetcodeLines(_meta(fixtureLeetcode('full')).leetcode!);
    expect(full.minutes, "LeetCode: today's minutes are used up");
    final no = leetcodeLines(_meta(fixtureLeetcode('unknown')).leetcode!);
    expect(no.minutes, 'LeetCode: minutes unknown');
    expect(no.credits, 'LeetCode credits today: unknown');
    expect(no.needed, 'LeetCode solves still owed today: unknown');
  });
}
