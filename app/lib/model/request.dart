/// `requests/{rid}/req|claim|result` (DOCS-contract §4).
library;

import 'package:tutor/model/json.dart';
import 'package:tutor/model/root.dart';

/// Serial queue a request runs in; a later rid never overtakes an earlier
/// one within a lane.
enum Lane {
  /// Session kinds.
  chat,

  /// Subject / plan / card kinds.
  build,
}

/// Request kinds and their lanes.
enum RequestKind {
  /// Draft a new subject from free text.
  subjectNew('subject_new', Lane.build),

  /// Redraft the plan from a comment.
  planRevise('plan_revise', Lane.build),

  /// Replace the plan's modules.
  planEdit('plan_edit', Lane.build),

  /// Approve the draft plan.
  planApprove('plan_approve', Lane.build),

  /// Go deeper or review only after the last module.
  subjectFinish('subject_finish', Lane.build),

  /// Edit or add a card.
  cardEdit('card_edit', Lane.build),

  /// Bring back a card the tutor removed.
  cardRestore('card_restore', Lane.build),

  /// Remove (suspend) a card the tutor added.
  cardRemove('card_remove', Lane.build),

  /// Start a teaching session.
  sessionStart('session_start', Lane.chat),

  /// Continue a past session.
  sessionResume('session_resume', Lane.chat),

  /// A learner message.
  message('message', Lane.chat),

  /// Next card (stops this session, starts a new one).
  next('next', Lane.chat),

  /// Stop the session.
  stop('stop', Lane.chat),

  /// Manual card-done override.
  cardDone('card_done', Lane.chat),

  /// Model-free fallback: next pick-an-answer question.
  drillNext('drill_next', Lane.chat),

  /// Model-free fallback: grade a pick.
  drillAnswer('drill_answer', Lane.chat),

  /// Minutes AnkiDroid reviews earned today.
  ankiStatus('anki_status', Lane.chat);

  new(this.wire, this.lane);

  /// Name on the wire.
  final String wire;

  /// Lane it is served in.
  final Lane lane;

  /// Parses a wire name.
  static RequestKind parse(String s) => byWire(values, s, (k) => k.wire);
}

/// Worker progress, mirrored to `sessions/{sid}/meta.busy`.
enum Phase {
  /// Claimed, not started.
  claimed,

  /// Model turn running.
  thinking,

  /// Finding pictures.
  images,

  /// Vision-checking pictures.
  checkingImages('checking_images'),

  /// Writing the projection.
  publishing;

  new([this._wire]);

  final String? _wire;

  /// Name on the wire.
  String get wire => _wire ?? name;

  /// Parses a wire name.
  static Phase parse(String s) => byWire(values, s, (p) => p.wire);
}

/// `req`: written once by the client; a retry re-PUTs it unchanged.
class RequestReq {
  /// Creates a request; a null [created] writes the server timestamp.
  const new({
    required this.kind,
    required this.dev,
    required this.sentAt,
    required this.body,
    this.created,
  });

  /// Parses `req`.
  factory fromJson(Json j) => RequestReq(
    kind: RequestKind.parse(str(j, 'kind')),
    dev: str(j, 'dev'),
    created: intOr(j, 'created'),
    sentAt: integer(j, 'sent_at'),
    body: asJson(j['body'], 'body'),
  );

  /// Kind.
  final RequestKind kind;

  /// Sending device id.
  final String dev;

  /// Server receipt time (ms), once resolved.
  final int? created;

  /// Client time of the first Send press; retries keep it.
  final int sentAt;

  /// Kind-specific body (see `request_body.dart`).
  final Json body;

  /// Wire form.
  Json toJson() => {
    'kind': kind.wire,
    'dev': dev,
    'created': created ?? serverTimestamp,
    'sent_at': sentAt,
    'body': body,
  };
}

/// `claim` (worker-written).
class RequestClaim {
  /// Creates the record.
  const new({
    required this.by,
    required this.leaseUntil,
    required this.attempt,
    required this.phase,
    required this.at,
  });

  /// Parses `claim`.
  factory fromJson(Json j) => RequestClaim(
    by: str(j, 'by'),
    leaseUntil: integer(j, 'lease_until'),
    attempt: integer(j, 'attempt'),
    phase: Phase.parse(str(j, 'phase')),
    at: integer(j, 'at'),
  );

  /// Worker device id.
  final String by;

  /// Lease end (worker clock, ms).
  final int leaseUntil;

  /// Attempt number (>3 gives up).
  final int attempt;

  /// Current phase.
  final Phase phase;

  /// When the phase was set.
  final int at;

  /// Wire form.
  Json toJson() => {
    'by': by,
    'lease_until': leaseUntil,
    'attempt': attempt,
    'phase': phase.wire,
    'at': at,
  };
}

/// `result` (worker-written; final).
class RequestResult {
  /// Creates the record.
  const new({
    required this.ok,
    required this.at,
    this.data = const {},
    this.code,
    this.error,
    this.retry = false,
  });

  /// Parses `result`.
  factory fromJson(Json j) => RequestResult(
    ok: flag(j, 'ok'),
    at: integer(j, 'at'),
    data: objOr(j, 'data') ?? const {},
    code: strOr(j, 'code'),
    error: strOr(j, 'error'),
    retry: flag(j, 'retry'),
  );

  /// Success.
  final bool ok;

  /// When the worker finished.
  final int at;

  /// Kind-specific result data.
  final Json data;

  /// Error code (see `relay/error_text.dart`).
  final String? code;

  /// Human-readable error, shown to kuhy.
  final String? error;

  /// Whether the worker suggests retrying.
  final bool retry;

  /// Wire form.
  Json toJson() => compact({
    'ok': ok,
    'at': at,
    'data': data.isEmpty ? null : data,
    'code': code,
    'error': error,
    if (!ok) 'retry': retry,
  });
}
