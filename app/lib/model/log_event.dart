/// `log/{dev}/{eid}` events (curriculum §4): append-only, immutable.
library;

import 'package:tutor/model/grade.dart';
import 'package:tutor/model/json.dart';

export 'package:tutor/model/grade.dart';

/// `src` of a review the PC drill wrote (`tutor/drill.py`).
const String drillSource = 'drill';

/// One log event. [subject] and [card] say which card; [at] is the device
/// wall clock when it happened (ms).
sealed class LogEvent {
  const new({required this.subject, required this.card, required this.at});

  /// Parses an event by its `k` first: a kind may carry no card (`new_cap`
  /// from Settings), so `s`/`c` are read per kind. Unknown kinds throw, and
  /// the log skips them (an older app meets a newer event).
  factory fromJson(Object? v) {
    final j = asJson(v, 'event');
    final k = str(j, 'k');
    final at = integer(j, 'at');
    String s() => str(j, 's');
    String c() => str(j, 'c');
    return switch (k) {
      'review' => ReviewEvent(
        subject: s(),
        card: c(),
        at: at,
        grade: Grade.parse(integer(j, 'r')),
        rev: integer(j, 'rev'),
        durMs: intOr(j, 'dur_ms'),
        src: strOr(j, 'src'),
      ),
      'review_undo' => ReviewUndoEvent(
        subject: s(),
        card: c(),
        at: at,
        of: str(j, 'of'),
      ),
      'flag' => FlagEvent(
        subject: s(),
        card: c(),
        at: at,
        rev: integer(j, 'rev'),
        reason: strOr(j, 'reason') ?? '',
      ),
      'taught' => TaughtEvent(
        subject: s(),
        card: c(),
        at: at,
        session: strOr(j, 'session'),
      ),
      'untaught' => UntaughtEvent(subject: s(), card: c(), at: at),
      'new_cap' => NewCapEvent(n: integer(j, 'n'), at: at),
      _ => throw FormatException('unknown event kind "$k"'),
    };
  }

  /// Subject id.
  final String subject;

  /// Card id.
  final String card;

  /// Device wall clock (ms).
  final int at;

  /// `subject/card`, the fold's per-card key.
  String get key => '$subject/$card';

  /// Wire form.
  Json toJson();
}

/// A spaced-review answer (any device, offline OK).
class ReviewEvent extends LogEvent {
  /// Creates the event.
  const new({
    required super.subject,
    required super.card,
    required super.at,
    required this.grade,
    required this.rev,
    this.durMs,
    this.src,
  });

  /// Rating.
  final Grade grade;

  /// Card rev shown.
  final int rev;

  /// Time to answer.
  final int? durMs;

  /// Where it came from: [drillSource] for a PC drill pick; the app sends
  /// none (a Review rating).
  final String? src;

  /// A pick in the PC's multiple-choice drill: it schedules like any
  /// review but never makes a card `reviewed` (curriculum §6).
  bool get isDrill => src == drillSource;

  @override
  Json toJson() => compact({
    'k': 'review',
    's': subject,
    'c': card,
    'r': grade.value,
    'at': at,
    'rev': rev,
    'dur_ms': durMs,
    'src': src,
  });
}

/// Review's Back: the review whose eid is [of] is ignored entirely by the
/// fold (FSRS, good, reviewed); an unknown [of] is a no-op.
class ReviewUndoEvent extends LogEvent {
  /// Creates the event.
  const new({
    required super.subject,
    required super.card,
    required super.at,
    required this.of,
  });

  /// eid of the undone review.
  final String of;

  @override
  Json toJson() => {
    'k': 'review_undo',
    's': subject,
    'c': card,
    'of': of,
    'at': at,
  };
}

/// "This card is wrong" (counts only while the card's rev is unchanged).
class FlagEvent extends LogEvent {
  /// Creates the event.
  const new({
    required super.subject,
    required super.card,
    required super.at,
    required this.rev,
    this.reason = '',
  });

  /// Card rev flagged.
  final int rev;

  /// kuhy's reason.
  final String reason;

  @override
  Json toJson() => {
    'k': 'flag',
    's': subject,
    'c': card,
    'rev': rev,
    'reason': reason,
    'at': at,
  };
}

/// The tutor finished teaching the card (worker only).
class TaughtEvent extends LogEvent {
  /// Creates the event.
  const new({
    required super.subject,
    required super.card,
    required super.at,
    this.session,
  });

  /// Session it was taught in.
  final String? session;

  @override
  Json toJson() => compact({
    'k': 'taught',
    's': subject,
    'c': card,
    'at': at,
    'session': session,
  });
}

/// Taught undone (worker only); the card leaves the review queue.
class UntaughtEvent extends LogEvent {
  /// Creates the event.
  const new({required super.subject, required super.card, required super.at});

  @override
  Json toJson() => {'k': 'untaught', 's': subject, 'c': card, 'at': at};
}

/// Settings' "New cards per day" = [n] (no card; the latest by `at` wins).
class NewCapEvent extends LogEvent {
  /// Creates the event.
  const new({required this.n, required super.at})
    : super(subject: '', card: '');

  /// New cards per day.
  final int n;

  @override
  Json toJson() => {'k': 'new_cap', 'n': n, 'at': at};
}

/// An event with its log identity: `log/{dev}/{eid}`.
class LoggedEvent {
  /// Creates the pair.
  const new({required this.dev, required this.eid, required this.event});

  /// Writing device.
  final String dev;

  /// ULID (sortable, device clock).
  final String eid;

  /// The event.
  final LogEvent event;
}
