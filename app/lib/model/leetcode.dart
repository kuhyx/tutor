/// `meta.leetcode`: the LeetCode accounting a theory lesson carries
/// (kuhy, 2026-11-22). Absent on every other session. A count the server
/// could not check is missing on the wire and null here: "unknown", never 0.
library;

import 'package:tutor/model/json.dart';

/// The unit being taught and what it earns towards LeetCode today.
class LeetcodeMeta {
  /// Creates the record.
  const new({
    required this.unit,
    required this.taught,
    required this.total,
    required this.full,
    this.into,
    this.perCredit,
    this.credits,
    this.needed,
  });

  /// Parses `meta.leetcode`.
  factory fromJson(Object? v) {
    final j = asJson(v, 'leetcode');
    return LeetcodeMeta(
      unit: str(j, 'unit'),
      taught: integer(j, 'taught'),
      total: integer(j, 'total'),
      full: flag(j, 'full'),
      into: intOr(j, 'into'),
      perCredit: intOr(j, 'per_credit'),
      credits: intOr(j, 'credits'),
      needed: intOr(j, 'needed'),
    );
  }

  /// The unit's name (content).
  final String unit;

  /// Cards of the unit taught so far.
  final int taught;

  /// Cards in the unit.
  final int total;

  /// The day's minutes are used up: no more count towards a credit.
  final bool full;

  /// Minutes into the next credit; null = could not check.
  final int? into;

  /// Minutes that make a credit; null = could not check.
  final int? perCredit;

  /// Theory credits minted today; null = could not check.
  final int? credits;

  /// Solves still owed today; null = could not check.
  final int? needed;

  /// Wire form (a null count is left out, as RTDB stores no nulls).
  Json toJson() => compact({
    'unit': unit,
    'taught': taught,
    'total': total,
    'full': full,
    'into': into,
    'per_credit': perCredit,
    'credits': credits,
    'needed': needed,
  });
}
