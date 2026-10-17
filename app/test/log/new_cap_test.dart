// Settings' "New cards per day": a `new_cap` log event {"k","n","at"} (no
// card); the latest by `at` wins, 25 when there is none.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/log/new_cap.dart';
import 'package:tutor/model/log_event.dart';

LoggedEvent _e(String eid, LogEvent event) =>
    LoggedEvent(dev: 'd', eid: eid, event: event);

void main() {
  test('new_cap parses without s/c and round-trips', () {
    final e = LogEvent.fromJson({'k': 'new_cap', 'n': 40, 'at': 7});
    expect(e, isA<NewCapEvent>());
    expect((e as NewCapEvent).n, 40);
    expect(e.toJson(), {'k': 'new_cap', 'n': 40, 'at': 7});
    // Older kinds still need their card.
    expect(
      () => LogEvent.fromJson({'k': 'review', 'r': 3, 'at': 1, 'rev': 1}),
      throwsFormatException,
    );
  });

  test('new_cap outside 1..200 is dropped at parse, as the worker does', () {
    for (final n in [0, -3, 201]) {
      expect(
        () => LogEvent.fromJson({'k': 'new_cap', 'n': n, 'at': 1}),
        throwsFormatException,
        reason: 'n=$n',
      );
    }
    expect(
      (LogEvent.fromJson({'k': 'new_cap', 'n': 200, 'at': 1}) as NewCapEvent).n,
      200,
    );
  });

  test('effective cap: latest by at, else 25', () {
    expect(effectiveNewCap(const []), 25);
    expect(defaultNewCap, 25);
    final events = [
      _e('B', const NewCapEvent(n: 10, at: 200)),
      _e('C', const NewCapEvent(n: 60, at: 100)), // later eid, older at
      _e('A', const TaughtEvent(subject: 's', card: 'x', at: 50)),
    ];
    expect(effectiveNewCap(events), 10);
    // Same at: the later eid wins.
    expect(
      effectiveNewCap([
        _e('A', const NewCapEvent(n: 30, at: 5)),
        _e('B', const NewCapEvent(n: 31, at: 5)),
      ]),
      31,
    );
    // The fold ignores it.
    expect(
      fold(events, const {'s/x': CardInfo(rev: 1)}).scheduled,
      hasLength(1),
    );
  });
}
