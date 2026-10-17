/// The FSRS rating, 1..4 on the wire.
library;

/// FSRS rating.
enum Grade {
  /// Forgot.
  again(1),

  /// Recalled with effort.
  hard(2),

  /// Recalled.
  good(3),

  /// Trivial.
  easy(4);

  new(this.value);

  /// Wire value 1..4.
  final int value;

  /// Parses 1..4.
  static Grade parse(int v) => values.firstWhere(
    (g) => g.value == v,
    orElse: () => throw FormatException('rating $v not in 1..4'),
  );
}
