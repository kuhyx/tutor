/// What a review run shows: the due queue (all subjects, or one) and a
/// module's taught cards, from the folded event log.
library;

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

/// Every taught card of [module], due or not, in module order (the module
/// review); flagged and suspended cards are left out, as in [dueItems].
Future<List<ReviewItem>> moduleItems({
  required Catalog catalog,
  required EventLog events,
  required ModuleRef module,
}) async {
  final subjects = await catalog.cached();
  final s = subjects[module.subject];
  if (s == null) return const [];
  final folded = fold(await events.all(), cardInfos(subjects.values));
  return [
    for (final MapEntry(key: id, value: card) in s.cardsOf(module.module))
      if (!card.suspended &&
          folded.scheduled.containsKey('${s.id}/$id') &&
          !folded.flagged.contains('${s.id}/$id'))
        ?_item(subjects, '${s.id}/$id'),
  ];
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
