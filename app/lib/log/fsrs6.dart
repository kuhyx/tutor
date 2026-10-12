/// FSRS-6, ported from py-fsrs 6.3.2 `Scheduler` for exactly the contract's
/// configuration (curriculum §5): desired retention 0.9, no learning or
/// relearning steps, fuzzing off, maximum interval 36500 days.
///
/// Why a port and not the Dart `fsrs` package: fsrs 2.0.1 ships older
/// default weights AND clamps the Easy initial difficulty inside the
/// mean-reversion term, which py-fsrs 6.3.2 deliberately does not. Measured
/// 2026-10-12 against py-generated vectors: due +3 d vs +2 d after the first
/// review, difficulty off by 6e-3 after the second. The contract's rule is
/// "if Dart can't match, B3 ports py-fsrs's Scheduler", so this is that.
///
/// With no steps, a card's first review moves it straight to Review and it
/// never enters Relearning, so only those two paths exist here.
library;

import 'dart:math' as math;

import 'package:tutor/model/log_event.dart';

/// py-fsrs 6.3.2 `DEFAULT_PARAMETERS`.
const List<double> defaultWeights = [
  0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001, 1.8722, //
  0.1666, 0.796, 1.4835, 0.0614, 0.2629, 1.6483, 0.6014, 1.8729, 0.5425,
  0.0912, 0.0658, 0.1542,
];

const _stabilityMin = 0.001;
const _minDifficulty = 1.0;
const _maxDifficulty = 10.0;

/// A scheduled card (always in Review state once taught).
class FsrsCard {
  /// Creates the state.
  const new({
    required this.stability,
    required this.difficulty,
    required this.due,
    required this.lastReview,
  });

  /// Memory stability (days).
  final double stability;

  /// Difficulty 1..10.
  final double difficulty;

  /// Next due time (UTC).
  final DateTime due;

  /// Last review time (UTC).
  final DateTime lastReview;

  /// py-fsrs state name; always `review` without learning steps.
  String get state => 'review';
}

/// Python's `round()`: halves go to the even neighbour.
int roundHalfEven(double x) {
  final floor = x.floorToDouble();
  final diff = x - floor;
  if (diff != 0.5) return x.round();
  final f = floor.toInt();
  return f.isEven ? f : f + 1;
}

/// The scheduler.
class Fsrs6 {
  /// Creates it with [w] (21 weights).
  new({
    this.w = defaultWeights,
    this.desiredRetention = 0.9,
    this.maximumInterval = 36500,
  }) : _decay = -w[20],
       _factor = math.pow(0.9, 1 / -w[20]) - 1;

  /// Weights.
  final List<double> w;

  /// Target recall probability.
  final double desiredRetention;

  /// Longest interval (days).
  final int maximumInterval;

  final double _decay;
  final double _factor;

  double _clampS(double s) => math.max(s, _stabilityMin);

  double _clampD(double d) =>
      math.min(math.max(d, _minDifficulty), _maxDifficulty);

  double _initialDifficulty(int g, {required bool clamp}) {
    final d = w[4] - math.pow(math.e, w[5] * (g - 1)) + 1;
    return clamp ? _clampD(d) : d;
  }

  int _interval(double s) {
    final raw = (s / _factor) * (math.pow(desiredRetention, 1 / _decay) - 1);
    return math.min(math.max(roundHalfEven(raw), 1), maximumInterval);
  }

  FsrsCard _schedule(double s, double d, DateTime at) => FsrsCard(
    stability: s,
    difficulty: d,
    due: at.add(Duration(days: _interval(s))),
    lastReview: at,
  );

  /// The first review of a new card ([at] in UTC).
  FsrsCard first(Grade grade, DateTime at) => _schedule(
    _clampS(w[grade.value - 1]),
    _initialDifficulty(grade.value, clamp: true),
    at,
  );

  /// A later review of [card].
  FsrsCard review(FsrsCard card, Grade grade, DateTime at) {
    final g = grade.value;
    final days = at.difference(card.lastReview).inDays;
    final s = card.stability;
    final d = card.difficulty;
    final double next;
    if (days < 1) {
      var inc = math.pow(math.e, w[17] * (g - 3 + w[18])) * math.pow(s, -w[19]);
      if (g > 1) inc = math.max(inc, 1.0);
      next = s * inc;
    } else {
      final r = math.pow(1 + _factor * math.max(0, days) / s, _decay);
      next = g == 1
          ? math.min(
              w[11] *
                  math.pow(d, -w[12]) *
                  (math.pow(s + 1, w[13]) - 1) *
                  math.pow(math.e, (1 - r) * w[14]),
              s / math.pow(math.e, w[17] * w[18]),
            )
          : s *
                (1 +
                    math.pow(math.e, w[8]) *
                        (11 - d) *
                        math.pow(s, -w[9]) *
                        (math.pow(math.e, (1 - r) * w[10]) - 1) *
                        (g == 2 ? w[15] : 1) *
                        (g == 4 ? w[16] : 1));
    }
    return _schedule(_clampS(next), _nextDifficulty(d, g), at);
  }

  double _nextDifficulty(double d, int g) {
    final easy = _initialDifficulty(4, clamp: false);
    final delta = -(w[6] * (g - 3));
    final damped = d + (10.0 - d) * delta / 9.0;
    return _clampD(w[7] * easy + (1 - w[7]) * damped);
  }
}
