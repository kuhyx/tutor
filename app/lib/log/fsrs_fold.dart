/// The fold (curriculum §4/§5): log events -> FSRS state per card.
///
/// A pure function of the events and the catalog, identical to the Python
/// worker's (B2), checked against `contract/fsrs_vectors.json`. Fuzzing is
/// off and there are no learning steps, so every device replays the same
/// schedule from the same log.
library;

import 'package:tutor/log/fsrs6.dart';
import 'package:tutor/model/log_event.dart';

/// The scheduler both sides pin (curriculum §5); see `fsrs6.dart` for why
/// it is a port rather than the Dart `fsrs` package.
final Fsrs6 scheduler = Fsrs6();

/// A review closer than this to a kept review of the same card from a
/// different device is an offline double-tap and is dropped.
const int dedupeWindowMs = 60 * 1000;

/// What the fold needs from a catalog card.
class CardInfo {
  /// Creates the record.
  const new({required this.rev, this.suspended = false});

  /// Current card revision (flags count only for it).
  final int rev;

  /// Suspended cards never enter the review queue.
  final bool suspended;
}

/// The fold's output.
class FoldResult {
  /// Creates the result.
  const new({required this.scheduled, required this.flagged});

  /// FSRS card per taught `subject/card` key (untaught cards are absent).
  final Map<String, FsrsCard> scheduled;

  /// Keys with a flag on the card's current rev.
  final Set<String> flagged;
}

/// One entry of the review queue.
class DueCard {
  /// Creates the entry.
  const new(this.key, this.due);

  /// `subject/card`.
  final String key;

  /// When it fell due.
  final DateTime due;
}

DateTime _utc(int ms) => DateTime.fromMillisecondsSinceEpoch(ms, isUtc: true);

/// Merges every device's events, sorted by `(at, eid)`, minus double taps.
List<LoggedEvent> mergeEvents(Iterable<LoggedEvent> events) {
  final sorted = events.toList()
    ..sort((a, b) {
      final byAt = a.event.at.compareTo(b.event.at);
      return byAt != 0 ? byAt : a.eid.compareTo(b.eid);
    });
  final kept = <LoggedEvent>[];
  final reviews = <String, List<LoggedEvent>>{};
  // A review of an untaught card is ignored by the fold and never counts
  // for the dedupe either (curriculum §4.3).
  final taught = <String>{};
  for (final e in sorted) {
    final event = e.event;
    if (event is TaughtEvent) taught.add(event.key);
    if (event is UntaughtEvent) taught.remove(event.key);
    if (event is ReviewEvent && taught.contains(event.key)) {
      final prior = reviews.putIfAbsent(event.key, () => []);
      final doubleTap = prior.any(
        (p) => p.dev != e.dev && event.at - p.event.at < dedupeWindowMs,
      );
      if (doubleTap) continue;
      prior.add(e);
    }
    kept.add(e);
  }
  return kept;
}

/// Folds [events] against [cards] (keyed `subject/card`).
FoldResult fold(Iterable<LoggedEvent> events, Map<String, CardInfo> cards) {
  final scheduled = <String, FsrsCard>{};
  final flagged = <String>{};
  for (final e in mergeEvents(events)) {
    final event = e.event;
    final key = event.key;
    switch (event) {
      case TaughtEvent(:final at):
        // Taught (or re-taught): a new FSRS card reviewed Good at `at`.
        scheduled[key] = scheduler.first(Grade.good, _utc(at));
      case UntaughtEvent():
        scheduled.remove(key);
      case ReviewEvent(:final at, :final grade):
        final card = scheduled[key];
        if (card == null) continue; // a review of an untaught card
        scheduled[key] = scheduler.review(card, grade, _utc(at));
      case FlagEvent(:final rev):
        if (cards[key]?.rev == rev) flagged.add(key);
    }
  }
  return FoldResult(scheduled: scheduled, flagged: flagged);
}

/// Due cards from every subject: taught, `due <= now`, not flagged, not
/// suspended, in the catalog; oldest due first, no cap.
List<DueCard> reviewQueue(
  FoldResult result,
  Map<String, CardInfo> cards,
  DateTime now,
) {
  final due =
      <DueCard>[
        for (final entry in result.scheduled.entries)
          if (!entry.value.due.isAfter(now) &&
              !result.flagged.contains(entry.key) &&
              !(cards[entry.key]?.suspended ?? true))
            DueCard(entry.key, entry.value.due),
      ]..sort((a, b) {
        final byDue = a.due.compareTo(b.due);
        return byDue != 0 ? byDue : a.key.compareTo(b.key);
      });
  return due;
}
