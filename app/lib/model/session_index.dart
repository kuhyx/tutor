/// `session_index/{sid}`: one History row (DOCS-contract §6).
library;

import 'package:tutor/model/json.dart';

/// A card a session touched.
class IndexCard {
  /// Creates the record.
  const new({
    required this.id,
    required this.front,
    this.done = false,
    this.doneHere = false,
  });

  /// Parses an entry.
  factory fromJson(Object? v) {
    final j = asJson(v, 'card');
    return IndexCard(
      id: str(j, 'id'),
      front: str(j, 'front'),
      done: flag(j, 'done'),
      doneHere: flag(j, 'done_here'),
    );
  }

  /// Card id.
  final String id;

  /// Card front.
  final String front;

  /// Taught (anywhere).
  final bool done;

  /// Taught in this session.
  final bool doneHere;

  /// Wire form.
  Json toJson() => {
    'id': id,
    'front': front,
    'done': done,
    'done_here': doneHere,
  };
}

/// A History row.
class SessionIndexRow {
  /// Creates the record.
  const new({
    required this.started,
    required this.subject,
    required this.rev,
    this.cards = const [],
    this.activeMinutes = 0,
    this.creditedMinutes = 0,
    this.stopped = false,
    this.autoArchived = false,
  });

  /// Parses a row.
  factory fromJson(Json j) => SessionIndexRow(
    started: str(j, 'started'),
    subject: str(j, 'subject'),
    cards: listOf(j, 'cards', IndexCard.fromJson),
    activeMinutes: intOr(j, 'active_minutes') ?? 0,
    creditedMinutes: intOr(j, 'credited_minutes') ?? 0,
    stopped: flag(j, 'stopped'),
    autoArchived: flag(j, 'auto_archived'),
    rev: integer(j, 'rev'),
  );

  /// PC-local start `YYYY-MM-DD HH:MM`.
  final String started;

  /// Subject id.
  final String subject;

  /// Cards touched.
  final List<IndexCard> cards;

  /// Active minutes.
  final int activeMinutes;

  /// Credited minutes.
  final int creditedMinutes;

  /// Session stopped.
  final bool stopped;

  /// Auto-archived (hidden in History).
  final bool autoArchived;

  /// Projection revision.
  final int rev;

  /// Wire form.
  Json toJson() => compact({
    'started': started,
    'subject': subject,
    'cards': cards.isEmpty ? null : [for (final c in cards) c.toJson()],
    'active_minutes': activeMinutes,
    'credited_minutes': creditedMinutes,
    'stopped': stopped,
    'auto_archived': autoArchived,
    'rev': rev,
  });
}
