// `stats.today`'s own minutes, LeetCode minutes and the open outage window
// (DOCS-contract-carry.md "Stats", DOCS-contract-curriculum.md §7).
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/codes.dart';
import 'package:tutor/model/stats.dart';

const Map<String, Object?> _today = {
  'day': '2026-11-27',
  'credited_minutes': 15,
  'target': 15,
  'new': 0,
};

DateTime _at(int unixSeconds) =>
    DateTime.fromMillisecondsSinceEpoch(unixSeconds * 1000, isUtc: true);

void main() {
  test('own and LeetCode minutes parse; an older worker reads as 0', () {
    final t = Today.fromJson({..._today, 'own_minutes': 2, 'lc_minutes': 1});
    expect((t.ownMinutes, t.lcMinutes), (2, 1));
    final old = Today.fromJson(_today);
    expect((old.ownMinutes, old.lcMinutes), (0, 0));
    expect(old.unavailable, isNull);
  });

  test('the outage window parses with its reason', () {
    final t = Today.fromJson({
      ..._today,
      'unavailable': {'until': 1800, 'reason': 'rate_limit'},
    });
    final w = t.unavailable!;
    expect(w.until, 1800);
    expect(w.reason, UnavailableReason.rateLimit);
    final odd = Today.fromJson({
      ..._today,
      'unavailable': {'until': 1800, 'reason': 'solar flare'},
    });
    expect(odd.unavailable!.reason, UnavailableReason.other);
    final bare = Today.fromJson({
      ..._today,
      'unavailable': {'until': 1800},
    });
    expect(bare.unavailable!.reason, UnavailableReason.other);
    expect(
      Today.fromJson({..._today, 'unavailable': null}).unavailable,
      isNull,
    );
  });

  test('a window whose until has passed is clear', () {
    final t = Today.fromJson({
      ..._today,
      'unavailable': {'until': 1800, 'reason': 'overloaded'},
    });
    expect(t.unavailable!.openAt(_at(1799)), isTrue);
    expect(t.outageAt(_at(1799))?.reason, UnavailableReason.overloaded);
    expect(t.unavailable!.openAt(_at(1800)), isFalse);
    expect(t.outageAt(_at(1800)), isNull);
    expect(t.outageAt(_at(4000)), isNull);
    expect(Today.fromJson(_today).outageAt(_at(0)), isNull);
  });

  test('the wire form keeps all three', () {
    final j = {
      ..._today,
      'own_minutes': 3,
      'lc_minutes': 0,
      'unavailable': {'until': 99, 'reason': 'network'},
    };
    expect(Today.fromJson(j).toJson(), j);
  });
}
