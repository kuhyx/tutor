import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/log/fsrs6.dart';
import 'package:tutor/model/log_event.dart';

final _t0 = DateTime.fromMillisecondsSinceEpoch(1791731346000, isUtc: true);

void main() {
  final f = Fsrs6();

  test("Python's round(): halves go to even", () {
    expect(roundHalfEven(2.5), 2);
    expect(roundHalfEven(3.5), 4);
    expect(roundHalfEven(2.4), 2);
    expect(roundHalfEven(2.6), 3);
    expect(roundHalfEven(-0.5), 0);
  });

  test('first review: py-fsrs 6.3.2 values (Good -> S=w2, due +2 d)', () {
    final c = f.first(Grade.good, _t0);
    expect(c.stability, 2.3065);
    expect(c.difficulty, closeTo(2.118103970459016, 1e-12));
    expect(c.due, _t0.add(const Duration(days: 2)));
    expect(c.state, 'review');
  });

  test('same-day review uses short-term stability; Again may shrink it', () {
    final c = f.first(Grade.good, _t0);
    final again = f.review(c, Grade.again, _t0.add(const Duration(hours: 1)));
    expect(again.stability, lessThan(c.stability));
    final good = f.review(c, Grade.good, _t0.add(const Duration(hours: 1)));
    expect(good.stability, greaterThanOrEqualTo(c.stability));
    expect(again.due.difference(again.lastReview).inDays, greaterThan(0));
  });

  test('long-gap reviews: Again < Hard < Good < Easy stability', () {
    final c = f.first(Grade.good, _t0);
    final at = _t0.add(const Duration(days: 5));
    final s = [for (final g in Grade.values) f.review(c, g, at).stability];
    expect(s, orderedEquals([...s]..sort()));
    expect(f.review(c, Grade.easy, at).difficulty, lessThan(c.difficulty));
  });

  test('interval is clamped to [1, maximumInterval]', () {
    final short = Fsrs6(maximumInterval: 3);
    var c = short.first(Grade.easy, _t0);
    for (var i = 1; i < 6; i++) {
      c = short.review(c, Grade.easy, _t0.add(Duration(days: 30 * i)));
    }
    expect(c.due.difference(c.lastReview).inDays, 3);
    final tiny = Fsrs6(w: [0.0001, ...defaultWeights.skip(1)]);
    final first = tiny.first(Grade.again, _t0);
    expect(first.stability, 0.001);
    expect(first.due.difference(first.lastReview).inDays, 1);
  });
}
