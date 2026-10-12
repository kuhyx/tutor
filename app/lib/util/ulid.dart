/// ULIDs for `rid` / `eid` / `fid` (DOCS-contract §3): 26 Crockford base32
/// chars, 48-bit ms timestamp + 80 random bits, generated offline.
///
/// Monotonic: within one millisecond (or if the wall clock steps back) the
/// random part is incremented instead of redrawn, so ids from one device
/// sort in creation order. Log order and the fold's `(at, eid)` tie-break
/// depend on that.
library;

import 'dart:math';

const _alphabet = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

/// Generates monotonic ULIDs.
class UlidGenerator {
  /// Creates a generator; tests inject [now] (ms) and [random].
  new({int Function()? now, Random? random})
    : _now = now ?? (() => DateTime.now().millisecondsSinceEpoch),
      _random = random ?? Random.secure();

  final int Function() _now;
  final Random _random;
  int _lastTime = -1;
  List<int> _lastRandom = const [];

  /// The next id.
  String next() {
    var time = _now();
    if (time <= _lastTime) {
      time = _lastTime;
      _lastRandom = _increment(_lastRandom);
    } else {
      _lastTime = time;
      _lastRandom = List.generate(16, (_) => _random.nextInt(32));
    }
    return encodeTime(time) + _lastRandom.map((d) => _alphabet[d]).join();
  }

  static List<int> _increment(List<int> digits) {
    final out = List.of(digits);
    for (var i = out.length - 1; i >= 0; i--) {
      if (out[i] < 31) {
        out[i]++;
        return out;
      }
      out[i] = 0;
    }
    throw StateError('ULID random part overflowed within one millisecond');
  }
}

/// The 10-char time prefix for [ms]; also the smallest id at that time,
/// usable as a `startAt` bound.
String encodeTime(int ms) {
  if (ms < 0 || ms >= 1 << 48) {
    throw ArgumentError.value(ms, 'ms', 'outside the 48-bit ULID range');
  }
  final chars = List.filled(10, '0');
  var t = ms;
  for (var i = 9; i >= 0; i--) {
    chars[i] = _alphabet[t % 32];
    t ~/= 32;
  }
  return chars.join();
}

/// The timestamp (ms) a ULID was minted at.
int decodeTime(String ulid) {
  var t = 0;
  for (final ch in ulid.substring(0, 10).split('')) {
    final d = _alphabet.indexOf(ch);
    if (d < 0) throw FormatException('not a ULID: $ulid');
    t = t * 32 + d;
  }
  return t;
}
