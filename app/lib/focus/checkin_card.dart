/// The focus check-in card (DOCS-contract-focus.md, "Check-in card"): one
/// taught card of the active project's subjects, picked from local state.
library;

import 'package:tutor/home/catalog.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/review/review_items.dart';

/// Picks the check-in card, or null for the old "Still working?" tap.
typedef CheckinPicker = Future<ReviewItem?> Function();

/// The taught card of [subjects] that fell due first: the most overdue, or
/// (none due) the soonest due. Flagged and suspended cards are skipped, and
/// an untaught card is never picked. Null with no subjects or no taught card.
Future<ReviewItem?> pickCheckinCard({
  required Catalog catalog,
  required EventLog events,
  required List<String> subjects,
  required DateTime now,
}) async {
  if (subjects.isEmpty) return null;
  final all = await catalog.cached();
  final folded = fold(await events.all(), cardInfos(all.values));
  (String, DateTime)? best;
  for (final MapEntry(:key, value: fsrs) in folded.scheduled.entries) {
    final slash = key.indexOf('/');
    final subject = all[key.substring(0, slash)];
    final card = subject?.cards[key.substring(slash + 1)];
    final skip =
        subject == null ||
        card == null ||
        card.suspended ||
        !subjects.contains(subject.id) ||
        folded.flagged.contains(key);
    if (skip) continue;
    final due = fsrs.due;
    if (best == null ||
        due.isBefore(best.$2) ||
        (due == best.$2 && key.compareTo(best.$1) < 0)) {
      best = (key, due);
    }
  }
  if (best == null) return null;
  final key = best.$1;
  final slash = key.indexOf('/');
  final subject = all[key.substring(0, slash)]!;
  final id = key.substring(slash + 1);
  return ReviewItem(
    subject: subject.id,
    subjectTitle: subject.meta.title,
    cardId: id,
    card: subject.cards[id]!,
  );
}
