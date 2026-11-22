/// The spoken lines of the LeetCode stats in a lesson's top bar (the bar
/// itself is glyphs and numbers). "unknown" = the server could not check.
library;

import 'package:tutor/model/leetcode.dart';

/// One spoken line per stat.
typedef LeetcodeLines = ({
  String unit,
  String minutes,
  String credits,
  String needed,
  String cards,
});

String _n(int? n) => n == null ? 'unknown' : '$n';

/// The spoken lines of [m].
LeetcodeLines leetcodeLines(LeetcodeMeta m) {
  final into = m.into;
  final per = m.perCredit;
  return (
    unit: 'Unit: ${m.unit}',
    minutes: m.full
        ? "LeetCode: today's minutes are used up"
        : into == null || per == null
        ? 'LeetCode: minutes unknown'
        : 'LeetCode: $into of $per min to the next credit',
    credits: 'LeetCode credits today: ${_n(m.credits)}',
    needed: 'LeetCode solves still owed today: ${_n(m.needed)}',
    cards: 'Cards taught in this unit: ${m.taught} of ${m.total}',
  );
}
