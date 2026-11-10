import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/review/review_session.dart';
import 'package:tutor/ui/review_answer.dart';

/// The Focus screen's check-in card: the review run of the timer's pick (one
/// per pick), and Review's own card UI for it.
class CheckinCardRun {
  /// Creates the holder over the services; [_after] gets the timer's work
  /// for each rating (the screen reloads the server's figures after it).
  new(this._s, this._after);

  final TutorServices _s;
  final void Function(Future<void> work) _after;
  ReviewSession? _card;

  /// The run for the timer's current check-in card; null when it has none.
  /// Its rating is an ordinary review tagged `checkin`, and its time is the
  /// beat's.
  ReviewSession? run() {
    // A replaced run is left to the GC, not disposed: its rating may still
    // be finishing (it notifies after the timer has moved on).
    final timer = _s.focus;
    final item = timer.checkinCard;
    if (item == null) return _card = null;
    final run = _card;
    if (run != null && run.items.single == item) return run;
    return _card = ReviewSession(
      items: [item],
      events: _s.events,
      src: checkinSource,
      onRated: (at) => _after(timer.cardRated(at)),
      now: () => DateTime.fromMillisecondsSinceEpoch(timer.nowMs()),
    );
  }

  /// Releases the current run.
  void dispose() => _card?.dispose();

  /// Review's own card UI, without Back and Flag: the card leaves on its
  /// rating. Scrolls, as a revealed card can outgrow a phone screen.
  static Widget view(ReviewSession run) => ListenableBuilder(
    listenable: run,
    builder: (context, _) {
      final item = run.current;
      if (item == null) return const SizedBox.shrink();
      return SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            CardFace(item.card, revealed: run.revealed),
            const SizedBox(height: AppSpacing.sm),
            AnswerBar(run, onFlag: null),
          ],
        ),
      );
    },
  );
}
