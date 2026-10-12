/// `sessions/{sid}/meta` and `user` (DOCS-contract §6).
library;

import 'package:tutor/model/json.dart';
import 'package:tutor/model/request.dart';

/// The card a session teaches.
class CardRef {
  /// Creates the record.
  const new({required this.id, required this.front});

  /// Parses `{"id","front"}`.
  factory fromJson(Object? v) {
    final j = asJson(v, 'card');
    return CardRef(id: str(j, 'id'), front: str(j, 'front'));
  }

  /// Card id.
  final String id;

  /// Card front.
  final String front;

  /// Wire form.
  Json toJson() => {'id': id, 'front': front};
}

/// `meta.clock`: the worker's engagement clock (display only on clients).
class EngagementClock {
  /// Creates the record.
  const new({
    required this.activeSeconds,
    required this.replyTimeoutS,
    this.pausedReason,
    this.awaitingSince,
  });

  /// Parses `clock`.
  factory fromJson(Json j) => EngagementClock(
    activeSeconds: dbl(j, 'active_seconds'),
    pausedReason: strOr(j, 'paused_reason'),
    awaitingSince: intOr(j, 'awaiting_since'),
    replyTimeoutS: intOr(j, 'reply_timeout_s') ?? 600,
  );

  /// Active seconds so far.
  final double activeSeconds;

  /// Why the clock is paused, if it is.
  final String? pausedReason;

  /// Waiting for kuhy since (ms).
  final int? awaitingSince;

  /// Reply timeout (600 s).
  final int replyTimeoutS;

  /// "Stalled" pill: awaiting longer than the timeout at [nowMs].
  bool stalledAt(int nowMs) =>
      awaitingSince != null && awaitingSince! + replyTimeoutS * 1000 < nowMs;

  /// Wire form.
  Json toJson() => compact({
    'active_seconds': activeSeconds,
    'paused_reason': pausedReason,
    'awaiting_since': awaitingSince,
    'reply_timeout_s': replyTimeoutS,
  });
}

/// `meta.busy`: a request in flight; [text] shows as a pending bubble.
class Busy {
  /// Creates the record.
  const new({
    required this.rid,
    required this.phase,
    required this.since,
    this.text,
  });

  /// Parses `busy`.
  factory fromJson(Json j) => Busy(
    rid: str(j, 'rid'),
    phase: Phase.parse(str(j, 'phase')),
    since: integer(j, 'since'),
    text: strOr(j, 'text'),
  );

  /// Request id.
  final String rid;

  /// Worker phase.
  final Phase phase;

  /// Since (ms).
  final int since;

  /// Pending learner text.
  final String? text;

  /// Wire form.
  Json toJson() =>
      compact({'rid': rid, 'phase': phase.wire, 'since': since, 'text': text});
}

/// `sessions/{sid}/meta`.
class SessionMeta {
  /// Creates the record.
  const new({
    required this.subject,
    required this.started,
    required this.n,
    required this.rev,
    required this.clock,
    this.card,
    this.stopped = false,
    this.cardDone = false,
    this.checkOpen = false,
    this.creditedMinutes = 0,
    this.busy,
  });

  /// Parses `meta`.
  factory fromJson(Json j) => SessionMeta(
    subject: str(j, 'subject'),
    card: j['card'] == null ? null : CardRef.fromJson(j['card']),
    started: integer(j, 'started'),
    stopped: flag(j, 'stopped'),
    cardDone: flag(j, 'card_done'),
    checkOpen: flag(j, 'check_open'),
    n: integer(j, 'n'),
    rev: integer(j, 'rev'),
    clock: EngagementClock.fromJson(asJson(j['clock'], 'clock')),
    creditedMinutes: intOr(j, 'credited_minutes') ?? 0,
    busy: objOr(j, 'busy') == null ? null : Busy.fromJson(objOr(j, 'busy')!),
  );

  /// Subject id.
  final String subject;

  /// Card being taught.
  final CardRef? card;

  /// Start time (ms).
  final int started;

  /// Session stopped.
  final bool stopped;

  /// The card was taught.
  final bool cardDone;

  /// A check question is open.
  final bool checkOpen;

  /// Message count.
  final int n;

  /// Projection revision.
  final int rev;

  /// Engagement clock.
  final EngagementClock clock;

  /// Verified minutes credited.
  final int creditedMinutes;

  /// Request in flight.
  final Busy? busy;

  /// Wire form.
  Json toJson() => compact({
    'subject': subject,
    'card': card?.toJson(),
    'started': started,
    'stopped': stopped,
    'card_done': cardDone,
    'check_open': checkOpen,
    'n': n,
    'rev': rev,
    'clock': clock.toJson(),
    'credited_minutes': creditedMinutes,
    'busy': busy?.toJson(),
  });
}

/// `sessions/{sid}/user` (client-written).
class SessionUser {
  /// Creates the record.
  const new({this.archived = false});

  /// Parses `user`.
  factory fromJson(Json j) => SessionUser(archived: flag(j, 'archived'));

  /// Hidden from History by default.
  final bool archived;

  /// Wire form.
  Json toJson() => {'archived': archived};
}
