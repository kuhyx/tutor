// Fold step 7 (DOCS-contract-struggle.md §3): the trailing run of Again
// since the latest `taught`, after dedupe and undo, at the card's rev only.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/model/log_event.dart';

const _a = 'dev-a';
const _b = 'dev-b';
const _pc = 'dev-pc';
const int _day = 24 * 3600 * 1000;
const _t0 = 1791731346000;
const _key = 's/x';

int _n = 0;
LoggedEvent _e(String dev, LogEvent event) => LoggedEvent(
  dev: dev,
  eid: 'E${(_n++).toString().padLeft(6, '0')}',
  event: event,
);
LoggedEvent _taught(int at) =>
    _e(_pc, TaughtEvent(subject: 's', card: 'x', at: at));
LoggedEvent _rev(
  int at,
  Grade g, {
  int rev = 1,
  String dev = _a,
  String? src,
}) => _e(
  dev,
  ReviewEvent(subject: 's', card: 'x', at: at, grade: g, rev: rev, src: src),
);

int _struggle(List<LoggedEvent> events, {int rev = 1}) =>
    fold(events, {_key: CardInfo(rev: rev)}).struggleOf(_key);

/// Reviews [grades] a day apart, starting a day after `taught`.
List<LoggedEvent> _run(List<Grade> grades, {int rev = 1}) => [
  _taught(_t0),
  for (final (i, g) in grades.indexed) _rev(_t0 + (i + 1) * _day, g, rev: rev),
];

void main() {
  const again = Grade.again;
  const good = Grade.good;

  test('three Again ratings -> 3; untaught or never reviewed -> 0', () {
    expect(_struggle(_run([again, again, again])), 3);
    expect(_struggle(_run([])), 0);
    expect(_struggle([_rev(_t0, again)]), 0); // never taught
    expect(
      _struggle([
        ..._run([again, again]),
        _e(
          _pc,
          const UntaughtEvent(subject: 's', card: 'x', at: _t0 + _day * 9),
        ),
      ]),
      0,
    );
  });

  test('Again, Again, Good, Again -> 1 (a kept Good ends the run)', () {
    expect(_struggle(_run([again, again, good, again])), 1);
    expect(_struggle(_run([again, Grade.hard])), 0);
  });

  test('reviews at an old rev neither count nor end the run', () {
    final events = [
      _taught(_t0),
      _rev(_t0 + _day, again),
      _rev(_t0 + 2 * _day, again),
      _rev(_t0 + 3 * _day, again, rev: 2),
      _rev(_t0 + 4 * _day, good), // old rev: does not end it
      _rev(_t0 + 5 * _day, again, rev: 2),
    ];
    expect(_struggle(events, rev: 2), 2);
    expect(_struggle(events), 0); // at rev 1: the Good ends the run
    expect(_struggle(_run([again, again, again]), rev: 2), 0); // an edit
  });

  test('a review_undo pops the Again it names', () {
    final events = _run([again, again, again]);
    final undo = _e(
      _a,
      ReviewUndoEvent(
        subject: 's',
        card: 'x',
        at: _t0 + 10 * _day,
        of: events.last.eid,
      ),
    );
    expect(_struggle([...events, undo]), 2);
  });

  test('a cross-device double tap < 60 s counts once; 60 s counts twice', () {
    const t = _t0 + _day;
    expect(
      _struggle([
        _taught(_t0),
        _rev(t, again),
        _rev(t + 59999, again, dev: _b),
      ]),
      1,
    );
    expect(
      _struggle([
        _taught(_t0),
        _rev(t, again),
        _rev(t + 60000, again, dev: _b),
      ]),
      2,
    );
    // The same device twice within the window: both kept.
    expect(_struggle([_taught(_t0), _rev(t, again), _rev(t + 1, again)]), 2);
  });

  test('a re-teach resets; drill picks count', () {
    final events = _run([again, again, again]);
    expect(_struggle([...events, _taught(_t0 + 9 * _day)]), 0);
    expect(
      _struggle([
        ...events,
        _taught(_t0 + 9 * _day),
        _rev(_t0 + 10 * _day, again, src: drillSource),
      ]),
      1,
    );
  });
}
