/// Read mode (no model, DOCS-relay.md "read_next" / "read_rate"): the next
/// untaught card with its back and source, rated "got it" or "again".
library;

import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';

/// The two read ratings, as the wire names them.
enum ReadRating {
  /// Known: taught, due on the normal schedule.
  gotIt('got_it'),

  /// Not yet: taught plus a review rated Again (due within the day).
  again('again');

  new(this.wire);

  /// Wire name.
  final String wire;
}

/// `read_next`: the next card to read; null [subject] = any subject.
RequestBody readNext({String? subject}) =>
    RequestBody.raw(RequestKind.readNext, {'subject': subject});

/// `read_rate`: [rating] of the open card [promptId].
RequestBody readRate(String promptId, ReadRating rating) => RequestBody.raw(
  RequestKind.readRate,
  {'prompt_id': promptId, 'rating': rating.wire},
);

/// One card to read, both sides.
class ReadCard {
  /// Creates the card.
  const new({
    required this.subject,
    required this.id,
    required this.module,
    required this.front,
    required this.back,
    required this.excerpt,
    required this.source,
  });

  /// Parses `{subject, id, module, front, back, excerpt, source}`.
  factory fromJson(Json j) => ReadCard(
    subject: str(j, 'subject'),
    id: str(j, 'id'),
    module: str(j, 'module'),
    front: str(j, 'front'),
    back: str(j, 'back'),
    excerpt: str(j, 'excerpt'),
    source: str(j, 'source'),
  );

  /// Subject id.
  final String subject;

  /// Card id.
  final String id;

  /// Module id.
  final String module;

  /// The question side.
  final String front;

  /// The answer side.
  final String back;

  /// Verbatim source text.
  final String excerpt;

  /// Source link.
  final String source;
}

/// What `read_next` returned.
sealed class ReadNext {
  const new();

  /// Parses a `read_next` result: `{empty:true}` or a card to read.
  factory fromJson(Json j) =>
      flag(j, 'empty') ? const ReadEmpty() : ReadPrompt.fromJson(j);
}

/// Nothing left to read.
class ReadEmpty extends ReadNext {
  /// Creates the value.
  const new();
}

/// One open card.
class ReadPrompt extends ReadNext {
  /// Creates the prompt.
  const new({required this.promptId, required this.card, this.unavailable});

  /// Parses the `read_next` card shape.
  factory fromJson(Json j) {
    final unavailable = objOr(j, 'unavailable');
    return ReadPrompt(
      promptId: str(j, 'prompt_id'),
      card: ReadCard.fromJson(asJson(j['card'], 'card')),
      unavailable: unavailable == null
          ? null
          : Unavailable.fromJson(unavailable),
    );
  }

  /// Id to rate with.
  final String promptId;

  /// The card.
  final ReadCard card;

  /// The open outage window; null once Claude is back.
  final Unavailable? unavailable;
}
