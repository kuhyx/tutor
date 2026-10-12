/// Offline FSRS review (curriculum §5): the due queue from the folded event
/// log, then front -> reveal -> Again/Hard/Good/Easy or Flag. Every answer
/// is an event queued locally first, so a phone with no network still
/// reviews; the queue is flushed best-effort after each answer.
library;

import 'dart:developer';

import 'package:flutter/foundation.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/model/card.dart';
import 'package:tutor/model/log_event.dart';

/// One card to review.
class ReviewItem {
  /// Creates the item.
  const new({
    required this.subject,
    required this.subjectTitle,
    required this.cardId,
    required this.card,
  });

  /// Subject id.
  final String subject;

  /// Subject title.
  final String subjectTitle;

  /// Card id.
  final String cardId;

  /// The card as shown.
  final StudyCard card;
}

/// Builds the due queue across all subjects.
Future<List<ReviewItem>> dueItems({
  required Catalog catalog,
  required EventLog events,
  required DateTime now,
}) async {
  final subjects = await catalog.cached();
  final infos = <String, CardInfo>{};
  for (final s in subjects.values) {
    for (final MapEntry(:key, :value) in s.cards.entries) {
      infos['${s.id}/$key'] = CardInfo(
        rev: value.rev,
        suspended: value.suspended,
      );
    }
  }
  final queue = reviewQueue(fold(await events.all(), infos), infos, now);
  return [for (final due in queue) ?_item(subjects, due.key)];
}

ReviewItem? _item(Map<String, SubjectData> subjects, String key) {
  final slash = key.indexOf('/');
  final s = subjects[key.substring(0, slash)];
  final card = s?.cards[key.substring(slash + 1)];
  if (s == null || card == null) return null;
  return ReviewItem(
    subject: s.id,
    subjectTitle: s.meta.title,
    cardId: key.substring(slash + 1),
    card: card,
  );
}

/// A review run over a fixed list of items.
class ReviewSession extends ChangeNotifier {
  /// Creates the run; [now] is injectable for tests.
  new({required this.items, required this.events, DateTime Function()? now})
    : _now = now ?? DateTime.now {
    _shownAt = _now();
  }

  /// The queue, fixed at start.
  final List<ReviewItem> items;

  /// Where answers go.
  final EventLog events;
  final DateTime Function() _now;
  late DateTime _shownAt;
  int _index = 0;
  bool _revealed = false;

  /// Answered or flagged so far.
  int get done => _index;

  /// The card on screen; null when the queue is finished.
  ReviewItem? get current => _index < items.length ? items[_index] : null;

  /// Whether the back is showing.
  bool get revealed => _revealed;

  /// Shows the back, excerpt and source.
  void reveal() {
    if (current == null || _revealed) return;
    _revealed = true;
    notifyListeners();
  }

  /// Rates the current card (only after [reveal]).
  Future<void> rate(Grade grade) async {
    final item = current;
    if (item == null || !_revealed) return;
    final at = _now();
    await events.record(
      ReviewEvent(
        subject: item.subject,
        card: item.cardId,
        at: at.millisecondsSinceEpoch,
        grade: grade,
        rev: item.card.rev,
        durMs: at.difference(_shownAt).inMilliseconds,
      ),
    );
    await _advance();
  }

  /// Flags the current card (wrong / unclear); it leaves the queue until
  /// the card is edited (a new rev clears the flag).
  Future<void> flag(String reason) async {
    final item = current;
    if (item == null) return;
    await events.record(
      FlagEvent(
        subject: item.subject,
        card: item.cardId,
        at: _now().millisecondsSinceEpoch,
        rev: item.card.rev,
        reason: reason.trim(),
      ),
    );
    await _advance();
  }

  Future<void> _advance() async {
    _index++;
    _revealed = false;
    _shownAt = _now();
    notifyListeners();
    try {
      await events.flush();
    } on Object catch (error) {
      // `on Object`: offline is normal here; the event stays queued and the
      // next flush (Home load, next answer) sends it.
      log('review flush failed; kept queued', level: 800, error: error);
    }
  }
}
