// The daily cap is gone (2026-11-22), but an old log still holds `new_cap`
// events: they parse, round-trip and change nothing in the fold.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/model/log_event.dart';

const _t0 = 1791731346000;

void main() {
  test('an old new_cap event parses and round-trips', () {
    final json = {'k': 'new_cap', 'n': 25, 'at': _t0};
    final event = LogEvent.fromJson(json);
    expect(event, isA<NewCapEvent>());
    expect((event as NewCapEvent).n, 25);
    expect(event.toJson(), json);
  });

  test('an out-of-range new_cap is refused at parse', () {
    expect(
      () => LogEvent.fromJson({'k': 'new_cap', 'n': 0, 'at': _t0}),
      throwsFormatException,
    );
  });

  test('the fold ignores an old new_cap event', () {
    const cards = {'s/x': CardInfo(rev: 1)};
    const taught = LoggedEvent(
      dev: 'pc',
      eid: 'E1',
      event: TaughtEvent(subject: 's', card: 'x', at: _t0),
    );
    const cap = LoggedEvent(
      dev: 'a',
      eid: 'E2',
      event: NewCapEvent(n: 3, at: _t0 + 1),
    );
    final without = fold([taught], cards);
    final withCap = fold([taught, cap], cards);
    expect(withCap.scheduled['s/x']!.due, without.scheduled['s/x']!.due);
  });
}
