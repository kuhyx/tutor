/// Per-card and per-module progress for the cards view and the Plan, from
/// the log fold (curriculum §4-§6) as the retired page showed it
/// (`progress.deck_summary`: done / total per topic, plus done per card).
///
/// Done = taught; recalled = `good` (§6: recalled Good 20 h or more after
/// being taught); due = taught, not flagged, `due <= now`. Suspended cards
/// are not counted anywhere.
library;

import 'package:tutor/home/catalog.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/model/plan.dart';

/// One card's state.
class CardProgress {
  /// Creates the record.
  const new({
    this.taught = false,
    this.mastered = false,
    this.due = false,
    this.flagged = false,
  });

  /// Taught (done) by the tutor.
  final bool taught;

  /// `good` (§6): real recall after a day.
  final bool mastered;

  /// Due for review now.
  final bool due;

  /// Flagged on its current rev (out of review until edited).
  final bool flagged;

  /// A short label for the card row.
  String get label => [
    if (mastered) 'recalled' else if (taught) 'done' else 'not taught yet',
    if (due) 'due',
    if (flagged) 'flagged',
  ].join(' · ');
}

/// Counts over a set of cards.
class Tally {
  /// Creates the tally.
  const new({this.cards = 0, this.taught = 0, this.mastered = 0, this.due = 0});

  /// Cards counted (not suspended).
  final int cards;

  /// Of them taught.
  final int taught;

  /// Of them recalled (`good`; the field keeps its old name).
  final int mastered;

  /// Of them due now.
  final int due;

  /// The sum of two tallies.
  Tally operator +(Tally o) => Tally(
    cards: cards + o.cards,
    taught: taught + o.taught,
    mastered: mastered + o.mastered,
    due: due + o.due,
  );

  /// "x done · z recalled · n due", for a row that names the card count.
  String get doneText => [
    '$taught done',
    '$mastered recalled',
    if (due > 0) '$due due',
  ].join(' · ');

  /// "x/y done · z recalled · n due" (empty for no cards).
  String get summary => cards == 0
      ? ''
      : [
          '$taught/$cards done',
          '$mastered recalled',
          if (due > 0) '$due due',
        ].join(' · ');
}

/// One subject's progress.
class SubjectProgress {
  /// Creates the record.
  const new({
    required this.cards,
    required this.modules,
    required this.total,
    this.review = const {},
  });

  /// Card id -> state (suspended cards absent).
  final Map<String, CardProgress> cards;

  /// Module id -> tally, every module of the plan.
  final Map<String, Tally> modules;

  /// The whole subject.
  final Tally total;

  /// Module id -> review state, every module of the plan.
  final Map<String, ModuleReview> review;
}

/// Where a module stands for its review (the "module Anki"). Only cards
/// that are neither suspended nor flagged count.
enum ModuleReview {
  /// A card is not taught yet (or the module has no card to review).
  open,

  /// Every card taught; not every card got Good/Easy in a review yet.
  done,

  /// Every card got Good or Easy in a review: the next module opens.
  reviewed,
}

/// A module to review, as Home, Plan and the no-card state name it.
class ModuleRef {
  /// Creates the reference.
  const new({required this.subject, required this.module, required this.title});

  /// [m] of subject [subject].
  factory of(String subject, Module m) =>
      ModuleRef(subject: subject, module: m.id, title: m.title);

  /// Subject id.
  final String subject;

  /// Module id.
  final String module;

  /// Module title (for the button and the Review title).
  final String title;
}

/// The fold's card info (rev for flags, suspended) for [subjects].
Map<String, CardInfo> cardInfos(Iterable<SubjectData> subjects) => {
  for (final s in subjects)
    for (final MapEntry(key: id, value: c) in s.cards.entries)
      '${s.id}/$id': CardInfo(rev: c.rev, suspended: c.suspended),
};

/// The fold over this device's copy of the log and the cached catalog.
Future<FoldResult> foldAll(EventLog events, Catalog catalog) async =>
    fold(await events.all(), cardInfos((await catalog.cached()).values));

/// [s]'s progress from [fold] at [now].
SubjectProgress subjectProgress(SubjectData s, FoldResult fold, DateTime now) {
  final cards = <String, CardProgress>{};
  final modules = <String, Tally>{};
  var total = const Tally();
  final review = <String, ModuleReview>{};
  for (final m in s.plan?.modules ?? const <Module>[]) {
    var tally = const Tally();
    // The module review counts only cards that can be reviewed.
    var (open, taught, reviewed) = (0, 0, 0);
    for (final MapEntry(key: id, value: card) in s.cardsOf(m.id)) {
      if (card.suspended) continue;
      final key = '${s.id}/$id';
      final fsrs = fold.scheduled[key];
      final flagged = fold.flagged.contains(key);
      if (!flagged) {
        open++;
        if (fsrs != null) taught++;
        if (fold.reviewed.contains(key)) reviewed++;
      }
      final p = CardProgress(
        taught: fsrs != null,
        mastered: fold.good.contains(key),
        due: fsrs != null && !flagged && !fsrs.due.isAfter(now),
        flagged: flagged,
      );
      cards[id] = p;
      tally += Tally(
        cards: 1,
        taught: p.taught ? 1 : 0,
        mastered: p.mastered ? 1 : 0,
        due: p.due ? 1 : 0,
      );
    }
    modules[m.id] = tally;
    total += tally;
    review[m.id] = open == 0 || taught < open
        ? ModuleReview.open
        : reviewed < open
        ? ModuleReview.done
        : ModuleReview.reviewed;
  }
  return SubjectProgress(
    cards: cards,
    modules: modules,
    total: total,
    review: review,
  );
}

/// The first module of [s] that is done but not reviewed and that the PC
/// has not marked `mastered` (the unlock already happened), or null.
ModuleRef? moduleToReview(SubjectData s, SubjectProgress p) {
  for (final m in s.plan?.modules ?? const <Module>[]) {
    if (p.review[m.id] == ModuleReview.done &&
        m.status != ModuleStatus.mastered) {
      return ModuleRef.of(s.id, m);
    }
  }
  return null;
}
