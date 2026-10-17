/// `subjects/{subj}/cards/{cid}` and `concepts` (curriculum §3).
library;

import 'package:tutor/model/json.dart';

/// A study card (worker-written; ids never renamed, cards never deleted).
class StudyCard {
  /// Creates the record.
  const new({
    required this.module,
    required this.order,
    required this.front,
    required this.back,
    required this.source,
    required this.excerpt,
    required this.rev,
    required this.origin,
    this.requires = const [],
    this.created,
    this.suspended = false,
    this.tutor,
  });

  /// Parses a card.
  factory fromJson(Object? v) {
    final j = asJson(v, 'card');
    return StudyCard(
      module: str(j, 'module'),
      order: integer(j, 'order'),
      front: str(j, 'front'),
      back: str(j, 'back'),
      source: str(j, 'source'),
      excerpt: str(j, 'excerpt'),
      requires: strings(j, 'requires'),
      rev: integer(j, 'rev'),
      origin: str(j, 'origin'),
      created: intOr(j, 'created'),
      suspended: flag(j, 'suspended'),
      tutor: objOr(j, 'tutor'),
    );
  }

  /// Module id.
  final String module;

  /// Order within the module.
  final int order;

  /// Question (<= 25 words).
  final String front;

  /// Answer (<= 30 words).
  final String back;

  /// https source URL.
  final String source;

  /// Verbatim excerpt from [source].
  final String excerpt;

  /// Same-subject card ids taught first.
  final List<String> requires;

  /// Revision; a flag only counts for the rev it was raised on.
  final int rev;

  /// `seed`, `generated` or `edited`.
  final String origin;

  /// Creation time (ms).
  final int? created;

  /// Hidden from teaching and review.
  final bool suspended;

  /// The tutor's mark: `{"added": ms}`, `{"removed": ms,
  /// "requires_of": {...}}` (curriculum §3); null = untouched.
  final Json? tutor;

  /// Suspended by the tutor: the Editor offers Restore.
  bool get removedByTutor => suspended && tutor?['removed'] != null;

  /// Added by the tutor and live: the Editor offers Remove.
  bool get addedByTutor => !suspended && tutor?['added'] != null;

  /// Wire form.
  Json toJson() => compact({
    'module': module,
    'order': order,
    'front': front,
    'back': back,
    'source': source,
    'excerpt': excerpt,
    'requires': requires.isEmpty ? null : requires,
    'rev': rev,
    'origin': origin,
    'created': created,
    'suspended': suspended,
    'tutor': tutor,
  });
}

/// One `concepts` entry (array, appended by the worker).
class Concept {
  /// Creates the record.
  const new({required this.name, required this.at, this.card, this.session});

  /// Parses an entry.
  factory fromJson(Object? v) {
    final j = asJson(v, 'concept');
    return Concept(
      name: str(j, 'name'),
      at: integer(j, 'at'),
      card: strOr(j, 'card'),
      session: strOr(j, 'session'),
    );
  }

  /// Concept name (free text: never a key).
  final String name;

  /// When mastered.
  final int at;

  /// Card it was mastered on.
  final String? card;

  /// Session it was mastered in.
  final String? session;

  /// Wire form.
  Json toJson() =>
      compact({'name': name, 'at': at, 'card': card, 'session': session});
}
