/// `sessions/{sid}/msgs/{m}` and `receipts/{r}` (DOCS-contract §6, §8).
library;

import 'package:tutor/model/json.dart';
import 'package:tutor/model/media.dart';

export 'package:tutor/model/media.dart' show Dgm, Img;

// `choices` is optional and forgiving: anything that is not a list of string
// lists is read as "no choices" for that question, never an error.
List<List<String>> _choicesOf(Json j) {
  final raw = j['choices'];
  if (raw is! List) return const [];
  return [
    for (final entry in raw)
      [
        if (entry is List)
          for (final c in entry)
            if (c is String && c.trim().isNotEmpty) c,
      ],
  ];
}

/// One transcript message. [role] is `tutor`, `learner` or `card`.
class Message {
  /// Creates the record.
  const new({
    required this.role,
    required this.text,
    this.at,
    this.questions = const [],
    this.choices = const [],
    this.lowEffort = false,
    this.check,
    this.checkResult,
    this.images = const [],
    this.diagrams = const [],
    this.masteredNew = const [],
    this.cardDone = false,
    this.rid,
    this.dev,
    this.cardId,
  });

  /// Parses a message.
  factory fromJson(Json j) => Message(
    role: str(j, 'role'),
    text: str(j, 'text'),
    at: intOr(j, 'at'),
    questions: strings(j, 'questions'),
    choices: _choicesOf(j),
    lowEffort: flag(j, 'low_effort'),
    check: objOr(j, 'check'),
    checkResult: objOr(j, 'check_result'),
    images: listOf(j, 'images', Img.fromJson),
    diagrams: listOf(j, 'diagrams', Dgm.fromJson),
    masteredNew: strings(j, 'mastered_new'),
    cardDone: flag(j, 'card_done'),
    rid: strOr(j, 'rid'),
    dev: strOr(j, 'dev'),
    cardId: strOr(j, 'card_id'),
  );

  /// `tutor`, `learner` or `card`.
  final String role;

  /// Markdown (raw HTML off when rendered).
  final String text;

  /// Time (ms).
  final int? at;

  /// Questions, each gets its own answer box.
  final List<String> questions;

  /// Tap-to-fill answers, aligned with [questions]: each entry is empty or
  /// three short strings. Older messages have none.
  final List<List<String>> choices;

  /// The tutor judged the answer low-effort.
  final bool lowEffort;

  /// `{"question","concept"}`.
  final Json? check;

  /// `{"passed","feedback"}`.
  final Json? checkResult;

  /// Pictures.
  final List<Img> images;

  /// Diagrams.
  final List<Dgm> diagrams;

  /// Concepts newly mastered in this turn.
  final List<String> masteredNew;

  /// The card was finished in this turn.
  final bool cardDone;

  /// Learner messages: request id.
  final String? rid;

  /// Learner messages: device id.
  final String? dev;

  /// Card messages: card id.
  final String? cardId;

  /// Wire form.
  Json toJson() => compact({
    'role': role,
    'text': text,
    'questions': questions.isEmpty ? null : questions,
    'choices': choices.any((c) => c.isNotEmpty) ? choices : null,
    'low_effort': lowEffort ? true : null,
    'check': check,
    'check_result': checkResult,
    'images': images.isEmpty ? null : [for (final i in images) i.toJson()],
    'diagrams': diagrams.isEmpty
        ? null
        : [for (final d in diagrams) d.toJson()],
    'mastered_new': masteredNew.isEmpty ? null : masteredNew,
    'card_done': cardDone ? true : null,
    'at': at,
    'rid': rid,
    'dev': dev,
    'card_id': cardId,
  });
}

/// `receipts/{r}`: a credit receipt (display only).
class Receipt {
  /// Creates the record.
  const new({
    required this.entryId,
    required this.recorded,
    required this.minutes,
    required this.minutesToday,
    required this.at,
    this.error,
  });

  /// Parses a receipt.
  factory fromJson(Json j) => Receipt(
    entryId: str(j, 'entry_id'),
    recorded: flag(j, 'recorded'),
    minutes: integer(j, 'minutes'),
    minutesToday: integer(j, 'minutes_today'),
    error: strOr(j, 'error'),
    at: integer(j, 'at'),
  );

  /// Ledger entry id `<sid>-m<n>`.
  final String entryId;

  /// Whether the ledger accepted it.
  final bool recorded;

  /// Minutes credited by this entry.
  final int minutes;

  /// Minutes today after it.
  final int minutesToday;

  /// Why it was refused.
  final String? error;

  /// When (ms).
  final int at;

  /// Wire form.
  Json toJson() => compact({
    'entry_id': entryId,
    'recorded': recorded,
    'minutes': minutes,
    'minutes_today': minutesToday,
    'error': error,
    'at': at,
  });
}
