/// The lock's `?` on a LeetCode problem: `rework_open` / `rework_turn`
/// bodies and results (tutor/relay/rework.py; DOCS-contract-coach.md
/// "Rework").
library;

import 'package:tutor/model/json.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/sql/lesson_models.dart';

/// One card the rework chat added.
typedef ReworkCard = ({String id, String front, String back});

/// An opened (or resumed) rework chat.
typedef ReworkOpened = ({
  String reworkId,
  String moduleTitle,
  String slug,
  List<Bubble> thread,
  List<ReworkCard> cards,
});

/// One answered turn: the reply and the cards it added.
typedef ReworkTurn = ({String replyMd, List<ReworkCard> cards});

/// `rework_open` on [module] of [subject] for the LeetCode [slug].
RequestBody reworkOpen(String subject, String module, String slug) =>
    RequestBody.raw(RequestKind.reworkOpen, {
      'subject': subject,
      'module': module,
      'slug': slug,
    });

/// `rework_turn`: what was unclear, in kuhy's words.
RequestBody reworkTurn(String reworkId, String text) => RequestBody.raw(
  RequestKind.reworkTurn,
  {'rework_id': reworkId, 'text': text},
);

ReworkCard _card(Object? v) {
  final j = asJson(v, 'card');
  return (id: str(j, 'id'), front: str(j, 'front'), back: str(j, 'back'));
}

/// Parses a `rework_open` result.
ReworkOpened parseReworkOpened(Json j) => (
  reworkId: str(j, 'rework_id'),
  moduleTitle: strOr(j, 'module_title') ?? str(j, 'module'),
  slug: str(j, 'slug'),
  thread: listOf(j, 'thread', parseBubble),
  cards: listOf(j, 'cards', _card),
);

/// Parses a `rework_turn` result.
ReworkTurn parseReworkTurn(Json j) =>
    (replyMd: strOr(j, 'reply_md') ?? '', cards: listOf(j, 'cards', _card));
