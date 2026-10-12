/// `stats` (curriculum §7, worker-written) and `feedback/{fid}` (§6).
library;

import 'package:tutor/model/json.dart';

/// `stats.today`: the header counters.
class Today {
  /// Creates the record.
  const new({
    required this.day,
    required this.creditedMinutes,
    required this.target,
    required this.newCards,
    required this.newCap,
    this.activeMinutes,
  });

  /// Parses `stats.today`.
  factory fromJson(Json j) => Today(
    day: str(j, 'day'),
    creditedMinutes: integer(j, 'credited_minutes'),
    activeMinutes: intOr(j, 'active_minutes'),
    target: integer(j, 'target'),
    newCards: integer(j, 'new'),
    newCap: integer(j, 'new_cap'),
  );

  /// PC-local date `YYYY-MM-DD`.
  final String day;

  /// Verified minutes today.
  final int creditedMinutes;

  /// Engaged minutes of today's sessions (null: an older worker).
  final int? activeMinutes;

  /// Daily target (60).
  final int target;

  /// Cards taught today.
  final int newCards;

  /// Daily new-card cap (10).
  final int newCap;

  /// Wire form.
  Json toJson() => {
    'day': day,
    'credited_minutes': creditedMinutes,
    'active_minutes': ?activeMinutes,
    'target': target,
    'new': newCards,
    'new_cap': newCap,
  };
}

/// One `stats.days` entry.
class DayStats {
  /// Creates the record.
  const new({
    required this.minutes,
    required this.taught,
    required this.reviews,
  });

  /// Parses a day.
  factory fromJson(Object? v) {
    final j = asJson(v, 'day');
    return DayStats(
      minutes: intOr(j, 'minutes') ?? 0,
      taught: intOr(j, 'taught') ?? 0,
      reviews: intOr(j, 'reviews') ?? 0,
    );
  }

  /// Credited minutes.
  final int minutes;

  /// Cards taught.
  final int taught;

  /// Reviews done.
  final int reviews;

  /// Wire form.
  Json toJson() => {'minutes': minutes, 'taught': taught, 'reviews': reviews};
}

/// `stats`.
class Stats {
  /// Creates the record.
  const new({required this.today, required this.days});

  /// Parses `stats`.
  factory fromJson(Json j) => Stats(
    today: Today.fromJson(asJson(j['today'], 'today')),
    days: mapOf(j, 'days', DayStats.fromJson),
  );

  /// Today's counters.
  final Today today;

  /// Per-day timeline keyed by date.
  final Map<String, DayStats> days;

  /// Wire form.
  Json toJson() => {
    'today': today.toJson(),
    'days': {for (final e in days.entries) e.key: e.value.toJson()},
  };
}

/// Feedback category.
enum FeedbackCategory {
  /// Layout or control problem.
  ui,

  /// Tutor answer problem.
  response,

  /// The learning experience.
  experience,

  /// Anything else.
  other,
}

/// `feedback/{fid}`: a developer report; never reaches the model.
class Feedback {
  /// Creates the record.
  const new({
    required this.category,
    required this.text,
    required this.dev,
    required this.at,
    required this.route,
    this.session,
    this.msg,
  });

  /// Parses a report.
  factory fromJson(Json j) => Feedback(
    category: byWire(
      FeedbackCategory.values,
      str(j, 'category'),
      (c) => c.name,
    ),
    text: str(j, 'text'),
    dev: str(j, 'dev'),
    at: integer(j, 'at'),
    route: str(j, 'route'),
    session: strOr(j, 'session'),
    msg: strOr(j, 'msg'),
  );

  /// Maximum [text] length.
  static const maxText = 4000;

  /// Category.
  final FeedbackCategory category;

  /// Report text (<= [maxText]).
  final String text;

  /// Reporting device.
  final String dev;

  /// Device time (ms).
  final int at;

  /// Screen it was filed from.
  final String route;

  /// Session it concerns.
  final String? session;

  /// Message key it concerns.
  final String? msg;

  /// Wire form.
  Json toJson() => compact({
    'category': category.name,
    'text': text,
    'session': session,
    'msg': msg,
    'dev': dev,
    'at': at,
    'route': route,
  });
}
