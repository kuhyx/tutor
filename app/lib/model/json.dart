/// Typed reads over decoded RTDB JSON.
///
/// RTDB content is untrusted (DOCS-contract §10): a wrong type is a
/// [FormatException] naming the field, never a cast error deep in a widget.
/// RTDB stores no nulls, so writers omit null fields ([compact]) and readers
/// treat absent as null.
library;

/// A decoded JSON object.
typedef Json = Map<String, dynamic>;

Never _bad(String key, Object? v, String want) =>
    throw FormatException('"$key": expected $want, got ${v.runtimeType}');

/// The object at the root of a value, or a [FormatException].
Json asJson(Object? v, [String what = 'value']) =>
    v is Map<String, dynamic> ? v : _bad(what, v, 'object');

/// Required string.
String str(Json j, String k) {
  final v = j[k];
  return v is String ? v : _bad(k, v, 'string');
}

/// Optional string.
String? strOr(Json j, String k) => j[k] == null ? null : str(j, k);

/// Required int (RTDB may hand back `3.0` for an int it stored).
int integer(Json j, String k) {
  final v = j[k];
  return v is num ? v.toInt() : _bad(k, v, 'number');
}

/// Optional int.
int? intOr(Json j, String k) => j[k] == null ? null : integer(j, k);

/// Required double.
double dbl(Json j, String k) {
  final v = j[k];
  return v is num ? v.toDouble() : _bad(k, v, 'number');
}

/// Optional double.
double? dblOr(Json j, String k) => j[k] == null ? null : dbl(j, k);

/// Bool, absent = [fallback].
bool flag(Json j, String k, {bool fallback = false}) {
  final v = j[k];
  if (v == null) return fallback;
  return v is bool ? v : _bad(k, v, 'bool');
}

/// Optional nested object.
Json? objOr(Json j, String k) => j[k] == null ? null : asJson(j[k], k);

/// List of [k] mapped by [f]; absent = empty.
List<T> listOf<T>(Json j, String k, T Function(Object? item) f) {
  final v = j[k];
  if (v == null) return const [];
  if (v is! List) _bad(k, v, 'array');
  return List.unmodifiable(v.map(f));
}

/// List of strings; absent = empty.
List<String> strings(Json j, String k) =>
    listOf(j, k, (v) => v is String ? v : _bad(k, v, 'string item'));

/// Map of [k] mapped by [f]; absent = empty.
Map<String, T> mapOf<T>(Json j, String k, T Function(Object? v) f) {
  final v = j[k];
  if (v == null) return const {};
  return Map.unmodifiable(asJson(v, k).map((key, v) => MapEntry(key, f(v))));
}

/// [m] without null values, as RTDB would store it.
Json compact(Map<String, Object?> m) => {
  for (final e in m.entries)
    if (e.value != null) e.key: e.value,
};

/// Parses an enum by its wire name.
T byWire<T extends Enum>(List<T> values, String wire, String Function(T) w) =>
    values.firstWhere(
      (v) => w(v) == wire,
      orElse: () => throw FormatException('unknown value "$wire"'),
    );
