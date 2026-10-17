/// Offline FSRS review (curriculum §5): the due queue from the folded event
/// log, then front -> reveal -> Again/Hard/Good/Easy or Flag. Every answer
/// is an event queued locally first, so a phone with no network still
/// reviews; the queue is flushed best-effort after each answer. Back undoes
/// the last rating (a `review_undo` event) and shows that card again.
library;

import 'dart:developer';

import 'package:flutter/foundation.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/review/review_items.dart';

export 'package:tutor/review/review_items.dart';

/// A review run over a fixed list of items.
class ReviewSession extends ChangeNotifier {
  /// Creates the run; [now] is injectable for tests. With [requeue] (the
  /// module review) a card rated Again or Hard comes back at the end of
  /// the run until it gets Good or Easy; the due queue does not requeue.
  new({
    required this.items,
    required this.events,
    this.requeue = false,
    DateTime Function()? now,
  }) : _now = now ?? DateTime.now,
       _queue = [...items] {
    _shownAt = _now();
  }

  /// The items the run started with.
  final List<ReviewItem> items;

  /// Where answers go.
  final EventLog events;

  /// Again/Hard put the card back at the end.
  final bool requeue;
  final DateTime Function() _now;
  final List<ReviewItem> _queue;
  final Set<String> _finished = {};
  late DateTime _shownAt;
  int _index = 0;
  bool _revealed = false;
  final List<_Step> _steps = [];
  Grade? _undone;

  /// Back can step to the previously rated card (never across a flag:
  /// a flag has no undo).
  bool get canBack => _steps.isNotEmpty;

  /// The rating Back took away from the card on screen (highlighted).
  Grade? get undoneGrade => _undone;

  /// Answered or flagged so far (a requeued card counts each time).
  int get done => _index;

  /// Cards finished: rated (Good/Easy when requeuing) or flagged.
  int get cardsDone => _finished.length;

  /// Cards still to show, requeued ones included.
  int get left => _queue.length - _index;

  /// The card on screen; null when the queue is finished.
  ReviewItem? get current => _index < _queue.length ? _queue[_index] : null;

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
    final logged = await events.record(
      ReviewEvent(
        subject: item.subject,
        card: item.cardId,
        at: at.millisecondsSinceEpoch,
        grade: grade,
        rev: item.card.rev,
        durMs: at.difference(_shownAt).inMilliseconds,
      ),
    );
    final again = requeue && grade.value < Grade.good.value;
    final key = '${item.subject}/${item.cardId}';
    final finished = !again && _finished.add(key);
    if (again) _queue.add(item);
    _steps.add(
      _Step(_index, logged.eid, grade, requeued: again, finished: finished),
    );
    await _advance();
  }

  /// Back: undoes the last rating (a `review_undo` naming its eid) and
  /// shows that card again, revealed, so a new rating replaces it. Steps
  /// are undone last-first, so a requeued copy is still the queue's last.
  Future<void> back() async {
    if (_steps.isEmpty) return;
    final step = _steps.removeLast();
    final item = _queue[step.index];
    await events.record(
      ReviewUndoEvent(
        subject: item.subject,
        card: item.cardId,
        at: _now().millisecondsSinceEpoch,
        of: step.eid,
      ),
    );
    if (step.requeued) _queue.removeLast();
    if (step.finished) _finished.remove('${item.subject}/${item.cardId}');
    _index = step.index;
    await _advance(to: step.grade);
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
    // A requeued card has no later copy (it goes back only when rated), so
    // a flag takes it out of the run for good.
    _finished.add('${item.subject}/${item.cardId}');
    _steps.clear();
    await _advance();
  }

  // Next card; [to] = Back re-showing a card rated [to] (revealed).
  Future<void> _advance({Grade? to}) async {
    if (to == null) _index++;
    _revealed = to != null;
    _undone = to;
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

/// One rating, as Back undoes it.
class _Step {
  const new(
    this.index,
    this.eid,
    this.grade, {
    required this.requeued,
    required this.finished,
  });

  final int index;
  final String eid;
  final Grade grade;
  final bool requeued;
  final bool finished;
}
