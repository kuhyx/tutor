import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/log/fsrs6.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/model/log_event.dart';

const _a = 'dev-a';
const _b = 'dev-b';
const int _day = 24 * 3600 * 1000;
const _t0 = 1791731346000;

int _n = 0;
LoggedEvent _e(String dev, LogEvent event) => LoggedEvent(
  dev: dev,
  eid: 'E${(_n++).toString().padLeft(6, '0')}',
  event: event,
);
TaughtEvent _taught(int at, [String c = 'x']) =>
    TaughtEvent(subject: 's', card: c, at: at);
ReviewEvent _rev(int at, Grade g, [String c = 'x']) =>
    ReviewEvent(subject: 's', card: c, at: at, grade: g, rev: 1);

const _cards = {
  's/x': CardInfo(rev: 1),
  's/y': CardInfo(rev: 2),
  's/z': CardInfo(rev: 1, suspended: true),
};

void main() {
  test('taught = Good at taught time; a review moves it on', () {
    final taughtOnly = fold([_e(_a, _taught(_t0))], _cards);
    final card = taughtOnly.scheduled['s/x']!;
    expect(card.state, 'review');
    expect(
      card.lastReview,
      DateTime.fromMillisecondsSinceEpoch(_t0, isUtc: true),
    );
    expect(card.due.isAfter(card.lastReview), isTrue);

    final reviewed = fold([
      _e(_a, _taught(_t0)),
      _e(_a, _rev(_t0 + 3 * _day, Grade.good)),
    ], _cards).scheduled['s/x']!;
    expect(reviewed.stability, greaterThan(card.stability));
  });

  test('review of an untaught card is ignored; untaught leaves queue', () {
    final r = fold([
      _e(_a, _rev(_t0, Grade.easy)),
      _e(_a, _taught(_t0 + 1)),
      _e(_a, const UntaughtEvent(subject: 's', card: 'x', at: _t0 + 2)),
      _e(_a, _rev(_t0 + 3, Grade.again)),
    ], _cards);
    expect(r.scheduled, isEmpty);
  });

  test('order is (at, eid), not arrival', () {
    final early = _e(_b, _taught(_t0));
    final late = _e(_a, _rev(_t0 + 2 * _day, Grade.again));
    final r1 = fold([late, early], _cards).scheduled['s/x']!;
    final r2 = fold([early, late], _cards).scheduled['s/x']!;
    expect(r1.due, r2.due);
    expect(r1.stability, r2.stability);
  });

  test('double tap: cross-device within 60 s dropped, same device kept', () {
    final base = [_e(_a, _taught(_t0))];
    const t = _t0 + 2 * _day;
    final kept = mergeEvents([
      ...base,
      _e(_a, _rev(t, Grade.good)),
      _e(_a, _rev(t + 1000, Grade.good)), // same device: kept
      _e(_b, _rev(t + 59999, Grade.hard)), // other device: dropped
      _e(_b, _rev(t + 61000 + 1000, Grade.hard)), // 61 s after last a: kept
    ]);
    expect(kept.length, 4);
    expect(kept.map((e) => e.dev).toList(), [_a, _a, _a, _b]);
    // Different cards never dedupe each other.
    final other = mergeEvents([
      _e(_a, _rev(t, Grade.good)),
      _e(_b, _rev(t + 10, Grade.good, 'y')),
    ]);
    expect(other, hasLength(2));
    // The boundary: exactly 60 000 ms apart is NOT "within 60 s" (kept).
    // B2's Python must read it the same way; the vectors would catch it.
    final edge = mergeEvents([
      _e(_a, _rev(t, Grade.good)),
      _e(_b, _rev(t + dedupeWindowMs, Grade.good)),
    ]);
    expect(edge, hasLength(2));
    // A review of a not-yet-taught card never counts for the dedupe: B's
    // review 30 s later (after the card was taught) is kept (§4.3).
    final early = mergeEvents([
      _e(_a, _rev(t, Grade.good, 'w')),
      _e(_a, _taught(t + 10000, 'w')),
      _e(_b, _rev(t + 30000, Grade.good, 'w')),
    ]);
    expect(early.map((e) => e.dev).toList(), [_a, _a, _b]);
  });

  test('flags count only on the current rev', () {
    final r = fold([
      _e(_a, const FlagEvent(subject: 's', card: 'x', at: 1, rev: 1)),
      _e(_a, const FlagEvent(subject: 's', card: 'y', at: 1, rev: 1)),
      _e(_a, const FlagEvent(subject: 's', card: 'q', at: 1, rev: 1)),
    ], _cards);
    expect(r.flagged, {'s/x'});
  });

  test('review queue: due, unflagged, unsuspended, known; by due', () {
    final r = fold([
      _e(_a, _taught(_t0)),
      _e(_a, _taught(_t0 + 1000, 'y')),
      _e(_a, _taught(_t0, 'z')),
      _e(_a, _taught(_t0, 'unknown')),
    ], _cards);
    final dueX = r.scheduled['s/x']!.due;
    expect(
      reviewQueue(r, _cards, dueX.subtract(const Duration(seconds: 1))),
      isEmpty,
    );
    final later = dueX.add(const Duration(days: 30));
    expect(reviewQueue(r, _cards, later).map((d) => d.key), ['s/x', 's/y']);
    final flagged = fold([
      _e(_a, _taught(_t0)),
      _e(_a, const FlagEvent(subject: 's', card: 'x', at: 2, rev: 1)),
    ], _cards);
    expect(reviewQueue(flagged, _cards, later), isEmpty);
    // Same due: ties break on key.
    final tie = fold([_e(_a, _taught(_t0, 'y')), _e(_a, _taught(_t0))], _cards);
    expect(reviewQueue(tie, _cards, later).map((d) => d.key), ['s/x', 's/y']);
  });

  test('scheduler settings match the contract', () {
    expect(scheduler.desiredRetention, 0.9);
    expect(scheduler.maximumInterval, 36500);
    expect(scheduler.w, defaultWeights);
    // A runtime (non-const) construction, which coverage can see.
    expect(CardInfo(rev: int.parse('2')).suspended, isFalse);
  });

  test('reviewed: any Good/Easy review after the latest taught, no gap', () {
    bool rev(List<LoggedEvent> es) => fold(es, _cards).reviewed.contains('s/x');
    final taught = _e(_a, _taught(_t0));
    expect(rev([taught]), isFalse);
    expect(rev([taught, _e(_a, _rev(_t0 + 1, Grade.good))]), isTrue);
    expect(rev([taught, _e(_a, _rev(_t0 + 1, Grade.easy))]), isTrue);
    expect(rev([taught, _e(_a, _rev(_t0 + 1, Grade.hard))]), isFalse);
    // Sticky: a later Again does not undo it (unlike `good`).
    final later = [
      taught,
      _e(_a, _rev(_t0 + 1, Grade.good)),
      _e(_a, _rev(_t0 + 2, Grade.again)),
    ];
    expect(rev(later), isTrue);
    expect(fold(later, _cards).good, isEmpty);
    // Re-taught or untaught clears it; a review before teaching is ignored.
    expect(rev([...later, _e(_a, _taught(_t0 + 3))]), isFalse);
    expect(
      rev([
        ...later,
        _e(_a, const UntaughtEvent(subject: 's', card: 'x', at: _t0 + 3)),
      ]),
      isFalse,
    );
    expect(
      rev([_e(_a, _rev(_t0, Grade.good)), _e(_a, _taught(_t0 + 1))]),
      isFalse,
    );
  });
}
