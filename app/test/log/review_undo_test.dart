// review_undo (Review's Back): the review it names is ignored entirely by
// the fold; an unknown `of` is a no-op.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/model/log_event.dart';

const _a = 'dev-a';
const _b = 'dev-b';
const _pc = 'dev-pc';
const int _day = 24 * 3600 * 1000;
const _t0 = 1791731346000;

int _n = 0;
LoggedEvent _e(String dev, LogEvent event) => LoggedEvent(
  dev: dev,
  eid: 'E${(_n++).toString().padLeft(6, '0')}',
  event: event,
);
TaughtEvent _taught(int at) => TaughtEvent(subject: 's', card: 'x', at: at);
ReviewEvent _rev(int at, Grade g) =>
    ReviewEvent(subject: 's', card: 'x', at: at, grade: g, rev: 1);

const _cards = {'s/x': CardInfo(rev: 1)};

void main() {
  test('review_undo: the named review is ignored entirely', () {
    final taught = _e(_pc, _taught(_t0));
    final wrong = _e(_a, _rev(_t0 + 3 * _day, Grade.good));
    final undo = _e(
      _a,
      ReviewUndoEvent(
        subject: 's',
        card: 'x',
        at: _t0 + 3 * _day + 5,
        of: wrong.eid,
      ),
    );
    final again = _e(_a, _rev(_t0 + 3 * _day + 9, Grade.again));
    final undone = fold([taught, wrong, undo, again], _cards);
    final plain = fold([
      taught,
      _e(_a, _rev(_t0 + 3 * _day + 9, Grade.again)),
    ], _cards);
    final card = undone.scheduled['s/x']!;
    final want = plain.scheduled['s/x']!;
    expect(
      (card.due, card.stability, card.difficulty),
      (want.due, want.stability, want.difficulty),
    );
    // The undone Good no longer makes the card good or reviewed.
    expect(undone.good, isEmpty);
    expect(undone.reviewed, isEmpty);
    // Undo with nothing after it: as if the review never happened.
    final only = fold([taught, wrong, undo], _cards);
    expect(only.reviewed, isEmpty);
    expect(
      only.scheduled['s/x']!.due,
      fold([taught], _cards).scheduled['s/x']!.due,
    );
    // An unknown `of` is a no-op.
    final stray = _e(
      _a,
      const ReviewUndoEvent(subject: 's', card: 'x', at: _t0 + 1, of: 'NOPE'),
    );
    expect(fold([taught, wrong, stray], _cards).reviewed, {'s/x'});
  });

  test(
    "an undone review never drops another device's review as a double tap",
    () {
      final wrong = _e(_a, _rev(_t0 + _day, Grade.good));
      final undo = _e(
        _a,
        ReviewUndoEvent(
          subject: 's',
          card: 'x',
          at: _t0 + _day + 1,
          of: wrong.eid,
        ),
      );
      final other = _e(_b, _rev(_t0 + _day + 2, Grade.hard));
      final kept = mergeEvents([_e(_pc, _taught(_t0)), wrong, undo, other]);
      expect(kept.map((e) => e.eid), contains(other.eid));
      expect(kept.map((e) => e.eid), isNot(contains(wrong.eid)));
    },
  );
}
