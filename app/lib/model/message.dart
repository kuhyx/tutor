/// `sessions/{sid}/msgs/{m}` and `receipts/{r}` (DOCS-contract §6, §8).
library;

import 'package:tutor/model/json.dart';

/// A Wikimedia picture with attribution (§8).
class Img {
  /// Creates the record.
  const new({
    required this.url,
    required this.title,
    required this.author,
    required this.licence,
    required this.pageUrl,
    this.licenceUrl,
    this.term,
  });

  /// Parses an `IMG`.
  factory fromJson(Object? v) {
    final j = asJson(v, 'image');
    return Img(
      url: str(j, 'url'),
      title: str(j, 'title'),
      author: str(j, 'author'),
      licence: str(j, 'licence'),
      licenceUrl: strOr(j, 'licence_url'),
      pageUrl: str(j, 'page_url'),
      term: strOr(j, 'term'),
    );
  }

  /// Only `https://upload.wikimedia.org/` is ever loaded.
  static const allowedPrefix = 'https://upload.wikimedia.org/';

  /// Thumbnail URL.
  final String url;

  /// Title.
  final String title;

  /// Author (plain text).
  final String author;

  /// Licence (plain text).
  final String licence;

  /// Licence link.
  final String? licenceUrl;

  /// Commons page (the attribution link).
  final String pageUrl;

  /// Search term that found it.
  final String? term;

  /// Whether [url] is on the image host allowlist.
  bool get loadable => url.startsWith(allowedPrefix);

  /// Wire form.
  Json toJson() => compact({
    'url': url,
    'title': title,
    'author': author,
    'licence': licence,
    'licence_url': licenceUrl,
    'page_url': pageUrl,
    'term': term,
  });
}

/// An inline worker-rendered SVG diagram (<= 8 KB).
class Dgm {
  /// Creates the record.
  const new({required this.title, required this.svg});

  /// Parses a `DGM`.
  factory fromJson(Object? v) {
    final j = asJson(v, 'diagram');
    return Dgm(title: str(j, 'title'), svg: str(j, 'svg'));
  }

  /// Title.
  final String title;

  /// SVG markup.
  final String svg;

  /// Wire form.
  Json toJson() => {'title': title, 'svg': svg};
}

/// One transcript message. [role] is `tutor`, `learner` or `card`.
class Message {
  /// Creates the record.
  const new({
    required this.role,
    required this.text,
    this.at,
    this.questions = const [],
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
