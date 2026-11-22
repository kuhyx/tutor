/// What a review run shows: the due queue (all subjects, or one), a
/// module's cards not yet passed, a module's due cards, and the module
/// gate's cards (`gate_cards`, curriculum §6), from the folded event log.
/// The module and gate lists pull the log first, so a card taught on another
/// device a minute ago is in, and one rated Good since never comes back.
library;

import 'dart:developer';

import 'package:tutor/home/catalog.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/model/card.dart';
import 'package:tutor/progress/card_progress.dart';

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

/// The module gate's review (curriculum §6): [items] of [subject], titled
/// [title]; it ends by itself once every card is passed.
class GateReview {
  /// Creates the review.
  const new({required this.subject, required this.items, this.title});

  /// Subject id.
  final String subject;

  /// The cards to pass ([gateItems]).
  final List<ReviewItem> items;

  /// The module (or subject) name for the app bar.
  final String? title;
}

/// Builds the due queue across all subjects, or only [subject]'s (a
/// Review button inside a subject never mixes in another subject's cards).
Future<List<ReviewItem>> dueItems({
  required Catalog catalog,
  required EventLog events,
  required DateTime now,
  String? subject,
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
  return [
    for (final due in queue)
      if (subject == null || due.key.startsWith('$subject/'))
        ?_item(subjects, due.key),
  ];
}

/// Every taught card of [module] not yet passed (no Good or Easy since it
/// was last taught), due or not, in module order (the module review);
/// flagged and suspended cards are left out, as in [dueItems].
Future<List<ReviewItem>> moduleItems({
  required Catalog catalog,
  required EventLog events,
  required ModuleRef module,
}) async {
  await _pull(events);
  final subjects = await catalog.cached();
  final s = subjects[module.subject];
  if (s == null) return const [];
  final folded = fold(await events.all(), cardInfos(subjects.values));
  return [
    for (final MapEntry(key: id, value: card) in s.cardsOf(module.module))
      if (!card.suspended &&
          folded.scheduled.containsKey('${s.id}/$id') &&
          !folded.reviewed.contains('${s.id}/$id') &&
          !folded.flagged.contains('${s.id}/$id'))
        ?_item(subjects, '${s.id}/$id'),
  ];
}

/// The cards of [module] that are in the due queue at [now] ([dueItems]'s
/// rule: taught, `due <= now`, not flagged, not suspended), in module order,
/// whether or not they were passed before: exactly the cards the signed
/// `review_due.json` counts as due (`DOCS-contract-review-due.md`).
Future<List<ReviewItem>> moduleDueItems({
  required Catalog catalog,
  required EventLog events,
  required ModuleRef module,
  required DateTime now,
}) async {
  await _pull(events);
  final subjects = await catalog.cached();
  final s = subjects[module.subject];
  if (s == null) return const [];
  final infos = cardInfos(subjects.values);
  final queue = reviewQueue(fold(await events.all(), infos), infos, now);
  final due = {for (final d in queue) d.key};
  return [
    for (final id in s.cardsOf(module.module).map((e) => e.key))
      if (due.contains('${s.id}/$id')) ?_item(subjects, '${s.id}/$id'),
  ];
}

/// The module gate's review: [cards] (the worker's `gate_cards` of
/// [subject], its order) minus the ones the newest log shows passed and
/// not due at [now] (rated since the worker answered); unknown, flagged and
/// suspended cards are left out.
Future<List<ReviewItem>> gateItems({
  required Catalog catalog,
  required EventLog events,
  required String subject,
  required List<String> cards,
  required DateTime now,
}) async {
  await _pull(events);
  final subjects = await catalog.cached();
  final infos = cardInfos(subjects.values);
  final folded = fold(await events.all(), infos);
  bool open(String key) {
    final memory = folded.scheduled[key];
    if (memory == null || folded.flagged.contains(key)) return false;
    if (infos[key]?.suspended ?? true) return false;
    return !folded.reviewed.contains(key) || !memory.due.isAfter(now);
  }

  return [
    for (final id in cards)
      if (open('$subject/$id')) ?_item(subjects, '$subject/$id'),
  ];
}

// The newest events of every device; offline, the cached log still serves.
Future<void> _pull(EventLog events) async {
  try {
    await events.pull();
  } on Exception catch (error) {
    log('review pull failed; using the cached log', level: 800, error: error);
  }
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
