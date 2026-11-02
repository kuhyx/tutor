/// `requests/{rid}/req|claim|result` (DOCS-contract §4).
library;

import 'package:tutor/model/json.dart';
import 'package:tutor/model/root.dart';

export 'package:tutor/model/request_reply.dart';

/// Serial queue a request runs in (a later rid never overtakes an earlier).
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

  /// Reopen a finished session for follow-up questions.
  followUpOpen('follow_up_open', Lane.chat),

  /// Manual card-done override.
  cardDone('card_done', Lane.chat),

  /// Model-free fallback: next pick-an-answer question.
  drillNext('drill_next', Lane.chat),

  /// Model-free fallback: grade a pick.
  drillAnswer('drill_answer', Lane.chat),

  /// Minutes AnkiDroid reviews earned today.
  ankiStatus('anki_status', Lane.chat),

  /// Focus projects: the active project, today's minutes, the gate list.
  focusStatus('focus_status', Lane.chat),

  /// Focus timer tap (start, checkin, stop) with the client's time.
  focusEvent('focus_event', Lane.chat),

  /// Create a focus project.
  focusCreate('focus_create', Lane.chat),

  /// Edit a focus project.
  focusUpdate('focus_update', Lane.chat),

  /// End a focus project early.
  focusEnd('focus_end', Lane.chat),

  /// SQL practice: drills and topics.
  sqlList('sql_list', Lane.chat),

  /// One drill (no reference SQL).
  sqlGet('sql_get', Lane.chat),

  /// Run the typed SQL against a drill.
  sqlRun('sql_run', Lane.chat),

  /// Check a typed output grid against a drill.
  sqlPredict('sql_predict', Lane.chat),

  /// One Socratic question about the typed SQL.
  sqlHint('sql_hint', Lane.chat),

  /// A new drill on a topic.
  sqlGenerate('sql_generate', Lane.chat),

  /// One turn of a guided SQL lesson.
  sqlLessonTurn('sql_lesson_turn', Lane.chat),

  /// Problem coach: due re-tests, recent problems, the live session.
  lcList('lc_list', Lane.chat),

  /// Problem coach: open a problem, or resume a session by its id.
  lcOpen('lc_open', Lane.chat),

  /// Problem coach: a chat message (`hint`, `reveal` and the like are
  /// plain text), or a "solved" claim with its explanation.
  lcTurn('lc_turn', Lane.chat),

  /// Problem coach: run code against the statement examples.
  lcRun('lc_run', Lane.chat),

  /// Problem coach: confirm the toolbox entries the post-mortem proposes.
  lcCards('lc_cards', Lane.chat);

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
