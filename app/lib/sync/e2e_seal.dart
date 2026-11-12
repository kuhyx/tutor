/// End-to-end encryption of the tutor's RTDB tree (DOCS-contract §12).
///
/// The Dart twin of `tutor/relay/e2e.py`; `contract/e2e_vectors.json` pins
/// both. Keys stay clear; every *unit* (a node one writer writes whole) is
/// stored as `{"_e2e": <blob>, <clear siblings>}`, the blob crdt_sync's
/// [E2eCipher] with the unit's full path as AAD. Clear siblings are only the
/// server timestamps (`req.created`, `result.at`, presence `seen`/`beat`).
/// A write the layout has no rule for throws: nothing new leaks by accident.
library;

import 'dart:convert';

import 'package:crdt_sync/crdt_sync.dart' show E2eCipher, E2eLayout;

/// The pre-e2e root (`tutor/v1`): read once by the worker's copy, never
/// deleted.
const String kOldRoot = 'tutor/v1';

/// Where the tutor's data lives now: `tutor/v1-e2e`.
final E2eLayout kE2eLayout = E2eLayout.of(kOldRoot);

/// The key a sealed unit keeps its blob under.
const String kSealedKey = '_e2e';

const List<String> _clear = [
  'meta',
  'rev',
  'migration',
  'requests/*/claim',
  'sessions/*/progress/rid',
];

const Map<String, Set<String>> _units = {
  'live': {},
  'prefs/*': {},
  'stats/*': {},
  'presence/workers/*': {'beat'},
  'presence/clients/*': {'seen'},
  'uploads/*/*': {},
  'requests/*/req': {'created'},
  'requests/*/result': {'at'},
  'sessions/*/meta/*': {},
  'sessions/*/msgs/*': {},
  'sessions/*/receipts/*': {},
  'sessions/*/user/*': {},
  'sessions/*/progress/steps/*': {},
  'session_index/*': {},
  'subjects/*/meta': {},
  'subjects/*/plan': {},
  'subjects/*/cards': {},
  'subjects/*/concepts': {},
  'log/*/*': {},
  'feedback/*': {},
};

/// A write the layout refuses (unknown path, or inside a sealed unit).
class E2eLayoutError implements Exception {
  /// Creates the error.
  const new(this.message);

  /// What was refused.
  final String message;

  @override
  String toString() => 'E2eLayoutError: $message';
}

/// Where a node falls in the layout.
enum E2eRuleKind {
  /// Stored as is (ids, counters, lease times).
  clear,

  /// Sealed whole.
  unit,

  /// Inside a unit: never written on its own.
  below,

  /// A map of clear keys above units.
  struct,

  /// No rule: refused on write.
  unknown,
}

/// The rule for one node.
class E2eRule {
  /// Creates the rule.
  const new(this.kind, [this.depth = 0, this.keep = const {}]);

  /// Its kind.
  final E2eRuleKind kind;

  /// For [E2eRuleKind.below]: how many segments the unit has.
  final int depth;

  /// For a unit: the fields kept clear.
  final Set<String> keep;
}

Object? _pruned(Object? value) {
  if (value is! Map) return value;
  final out = <String, Object?>{};
  for (final e in value.entries) {
    final v = _pruned(e.value);
    if (v != null) out[e.key as String] = v;
  }
  return out.isEmpty ? null : out;
}

/// [path]'s segments, empty ones dropped.
List<String> e2eParts(String path) =>
    path.split('/').where((s) => s.isNotEmpty).toList();

bool _matches(List<String> pattern, List<String> parts) {
  if (pattern.length != parts.length) return false;
  for (var i = 0; i < parts.length; i++) {
    if (pattern[i] != '*' && pattern[i] != parts[i]) return false;
  }
  return true;
}

/// The rule for the node at [parts] (relative to the e2e root).
E2eRule classifyE2e(List<String> parts) {
  for (final pattern in _clear) {
    final pat = pattern.split('/');
    if (pat.length <= parts.length &&
        _matches(pat, parts.sublist(0, pat.length))) {
      return const E2eRule(E2eRuleKind.clear);
    }
  }
  for (final entry in _units.entries) {
    final pat = entry.key.split('/');
    if (_matches(pat, parts)) {
      return E2eRule(E2eRuleKind.unit, pat.length, entry.value);
    }
    if (pat.length < parts.length &&
        _matches(pat, parts.sublist(0, pat.length))) {
      return E2eRule(E2eRuleKind.below, pat.length, entry.value);
    }
  }
  for (final pattern in [..._clear, ..._units.keys]) {
    final pat = pattern.split('/');
    if (parts.length < pat.length &&
        _matches(pat.sublist(0, parts.length), parts)) {
      return const E2eRule(E2eRuleKind.struct);
    }
  }
  return const E2eRule(E2eRuleKind.unknown);
}

/// The sealed unit [rel] lies strictly below, or null.
String? e2eUnitPath(String rel) {
  final parts = e2eParts(rel);
  final rule = classifyE2e(parts);
  return rule.kind == E2eRuleKind.below
      ? parts.sublist(0, rule.depth).join('/')
      : null;
}

/// Seals writes and opens reads under [root] with [cipher].
class TutorSealer {
  /// Creates the sealer.
  new(this.cipher, {String? root}) : root = root ?? kE2eLayout.prefix;

  /// The key's cipher.
  final E2eCipher cipher;

  /// The e2e root every relative path hangs off.
  final String root;

  String _aad(List<String> parts) => [root, ...parts].join('/');

  /// [value] as it may be stored at [rel]; throws [E2eLayoutError] for an
  /// unknown path.
  Future<Object?> seal(String rel, Object? value) =>
      _seal(e2eParts(rel), value);

  /// A PATCH body for [rel]: each (multi-segment) key sealed on its own.
  Future<Map<String, Object?>> sealPatch(
    String rel,
    Map<String, Object?> body,
  ) async {
    final base = e2eParts(rel);
    final kind = classifyE2e(base).kind;
    if (kind == E2eRuleKind.unit || kind == E2eRuleKind.below) {
      throw E2eLayoutError('PATCH into sealed unit $rel');
    }
    return {
      for (final e in body.entries)
        e.key: await _seal([...base, ...e2eParts(e.key)], e.value),
    };
  }

  Future<Object?> _seal(List<String> parts, Object? value) async {
    final rule = classifyE2e(parts);
    if (rule.kind == E2eRuleKind.clear || value == null) return value;
    if (rule.kind == E2eRuleKind.unit) {
      return await _sealUnit(parts, value, rule.keep);
    }
    if (rule.kind == E2eRuleKind.struct && value is Map) {
      return {
        for (final e in value.entries)
          e.key as String: await _seal([
            ...parts,
            ...e2eParts(e.key as String),
          ], e.value),
      };
    }
    throw E2eLayoutError(
      'no e2e rule for a ${value.runtimeType} at ${parts.join('/')} '
      '(${rule.kind.name})',
    );
  }

  Future<Map<String, Object?>?> _sealUnit(
    List<String> parts,
    Object raw,
    Set<String> keep,
  ) async {
    // As RTDB would keep it: no null members, no empty objects.
    final value = _pruned(raw);
    if (value == null) return null;
    var body = value;
    final clear = <String, Object?>{};
    if (value is Map && keep.isNotEmpty) {
      body = {
        for (final e in value.entries)
          if (!keep.contains(e.key)) e.key as String: e.value,
      };
      for (final e in value.entries) {
        if (keep.contains(e.key)) clear[e.key as String] = e.value;
      }
    }
    final blob = await cipher.seal(jsonEncode(body), path: _aad(parts));
    return {kSealedKey: blob, ...clear};
  }

  /// [value] read at [rel] with every unit in it opened. A unit that does
  /// not open reads as absent; legacy plaintext is returned as stored.
  Future<Object?> open(String rel, Object? value) =>
      _open(e2eParts(rel), value);

  Future<Object?> _open(List<String> parts, Object? value) async {
    final rule = classifyE2e(parts);
    switch (rule.kind) {
      case E2eRuleKind.unit:
        return await _openUnit(parts, value);
      case E2eRuleKind.below:
        throw E2eLayoutError('read below sealed unit: ${parts.join('/')}');
      case E2eRuleKind.struct when value is Map:
        final out = <String, Object?>{};
        for (final e in value.entries) {
          final v = await _open([...parts, e.key as String], e.value);
          if (v != null) out[e.key as String] = v;
        }
        return out;
      case E2eRuleKind.struct when value is List:
        return [
          for (var i = 0; i < value.length; i++)
            await _open([...parts, '$i'], value[i]),
        ];
      case _:
        return value;
    }
  }

  Future<Object?> _openUnit(List<String> parts, Object? value) async {
    if (value is! Map || value[kSealedKey] is! String) return value;
    try {
      final text = await cipher.open(
        value[kSealedKey] as String,
        path: _aad(parts),
      );
      final data = jsonDecode(text);
      if (data is! Map) return data;
      return <String, Object?>{
        ...data.cast<String, Object?>(),
        for (final e in value.entries)
          if (e.key != kSealedKey) e.key as String: e.value,
      };
    } on FormatException {
      // E2eDecryptError is one: tampered, moved, or another key.
      return null;
    }
  }
}
