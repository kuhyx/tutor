/// Results of the model-free fallback kinds (`drill_next`, `drill_answer`,
/// `anki_status`) and the `claude_unavailable` error body. Used while Claude
/// is out: the PC serves picks from the existing cards, no model involved.
library;

import 'package:tutor/model/json.dart';

/// `today`: the day's minutes as the drill shows them.
class DrillToday {
  /// Creates the value.
  const new({required this.activeMin, required this.creditedMin});

  /// Parses `{active_min, credited_min}`.
  factory fromJson(Json j) => DrillToday(
    activeMin: integer(j, 'active_min'),
    creditedMin: integer(j, 'credited_min'),
  );

  /// Active minutes today.
  final int activeMin;

  /// Credited minutes today.
  final int creditedMin;
}

/// Claude is out until [until] (`unavailable` in a drill result, or the
/// `claude_unavailable` error body's `resets_at` and `reason`).
class Unavailable {
  /// Creates the value.
  const new({this.until, this.reason});

  /// Parses `{until, reason}`.
  factory fromJson(Json j) =>
      Unavailable(until: integer(j, 'until'), reason: strOr(j, 'reason'));

  /// Parses an error body leniently: this only decorates an error that is
  /// already known to be `claude_unavailable`, so a missing or oddly typed
  /// field must not hide it. Reads the result itself, then its `data`.
  factory fromError(Json result) {
    final data = result['data'];
    Object? field(String k) =>
        result[k] ?? (data is Map<String, dynamic> ? data[k] : null);
    final at = field('resets_at');
    final why = field('reason');
    return Unavailable(
      until: at is num ? at.toInt() : null,
      reason: why is String ? why : null,
    );
  }

  /// Unix seconds when Claude is back; null when the PC did not say.
  final int? until;

  /// Why, as the PC worded it; null or empty when it did not say.
  final String? reason;

  /// The one-line banner: "Claude limit — back at HH:MM" (local time); with
  /// no reason "Claude unavailable" (and the time when it is known).
  String get banner {
    final label = (reason ?? '').trim().isEmpty
        ? 'Claude unavailable'
        : 'Claude limit';
    final at = until;
    if (at == null) return label;
    final t = DateTime.fromMillisecondsSinceEpoch(at * 1000);
    final hh = t.hour.toString().padLeft(2, '0');
    final mm = t.minute.toString().padLeft(2, '0');
    return '$label — back at $hh:$mm';
  }
}

/// The card a drill question is about.
class DrillCard {
  /// Creates the card.
  const new({required this.subject, required this.id, required this.front});

  /// Parses `{subject, id, front}`.
  factory fromJson(Json j) => DrillCard(
    subject: str(j, 'subject'),
    id: str(j, 'id'),
    front: str(j, 'front'),
  );

  /// Subject id.
  final String subject;

  /// Card id.
  final String id;

  /// The question side.
  final String front;
}

/// What `drill_next` returned.
sealed class DrillNext {
  const new();

  /// Parses a `drill_next` result: `{empty:true}` or a question.
  factory fromJson(Json j) =>
      flag(j, 'empty') ? const DrillEmpty() : DrillQuestion.fromJson(j);
}

/// Nothing to drill right now.
class DrillEmpty extends DrillNext {
  /// Creates the value.
  const new();
}

/// One pick-an-answer question.
class DrillQuestion extends DrillNext {
  /// Creates the question.
  const new({
    required this.promptId,
    required this.card,
    required this.options,
    required this.today,
    this.unavailable,
  });

  /// Parses the `drill_next` question shape.
  factory fromJson(Json j) {
    final unavailable = objOr(j, 'unavailable');
    return DrillQuestion(
      promptId: str(j, 'prompt_id'),
      card: DrillCard.fromJson(asJson(j['card'], 'card')),
      options: listOf(j, 'options', (o) {
        if (o is String) return o;
        throw FormatException('"options": expected string, got $o');
      }),
      today: DrillToday.fromJson(asJson(j['today'], 'today')),
      unavailable: unavailable == null
          ? null
          : Unavailable.fromJson(unavailable),
    );
  }

  /// Id to answer with.
  final String promptId;

  /// The card asked about.
  final DrillCard card;

  /// 2-4 candidate answers, in display order.
  final List<String> options;

  /// The day's minutes.
  final DrillToday today;

  /// Set while Claude is out.
  final Unavailable? unavailable;
}

/// `drill_answer`: how the pick went, and the card's back.
class DrillAnswer {
  /// Creates the answer.
  const new({
    required this.correct,
    required this.answerIndex,
    required this.back,
    required this.excerpt,
    required this.source,
    required this.minuteCredited,
    required this.today,
  });

  /// Parses a `drill_answer` result.
  factory fromJson(Json j) => DrillAnswer(
    correct: flag(j, 'correct'),
    answerIndex: integer(j, 'answer_index'),
    back: str(j, 'back'),
    excerpt: str(j, 'excerpt'),
    source: str(j, 'source'),
    minuteCredited: flag(j, 'minute_credited'),
    today: DrillToday.fromJson(asJson(j['today'], 'today')),
  );

  /// Whether the pick was right.
  final bool correct;

  /// The right option's index.
  final int answerIndex;

  /// The card's back.
  final String back;

  /// Verbatim source text.
  final String excerpt;

  /// Source link.
  final String source;

  /// Whether this answer earned a credited minute.
  final bool minuteCredited;

  /// The day's minutes after this answer.
  final DrillToday today;
}

/// `anki_status`: what AnkiDroid reviews earned today.
class AnkiStatus {
  /// Creates the status.
  const new({
    required this.creditedTodayMin,
    required this.eligibleTodayMin,
    this.lastSyncAt,
    this.unavailable,
  });

  /// Parses an `anki_status` result.
  factory fromJson(Json j) {
    final unavailable = objOr(j, 'unavailable');
    return AnkiStatus(
      creditedTodayMin: integer(j, 'credited_today_min'),
      eligibleTodayMin: integer(j, 'eligible_today_min'),
      lastSyncAt: intOr(j, 'last_sync_at'),
      unavailable: unavailable == null
          ? null
          : Unavailable.fromJson(unavailable),
    );
  }

  /// Minutes already credited from Anki today.
  final int creditedTodayMin;

  /// Minutes Anki could credit today in all.
  final int eligibleTodayMin;

  /// Unix seconds of the PC's last Anki sync.
  final int? lastSyncAt;

  /// Set while Claude is out.
  final Unavailable? unavailable;
}
