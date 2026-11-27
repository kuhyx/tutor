/// Small reads/writes several screens share: `prefs`, `stats`.
library;

import 'dart:convert';
import 'dart:developer';

import 'package:tutor/model/ids.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/put_outbox.dart';
import 'package:tutor/sync/rtdb_client.dart';

/// Picks the subject new material comes from (`prefs.current_subject`,
/// client-written, last writer wins): kept on this install at once and
/// pushed by [outbox] when the database answers.
Future<void> setCurrentSubject(PutOutbox outbox, String subject) async {
  if (!isSlug(subject)) throw ArgumentError.value(subject, 'subject');
  await outbox.put(currentSubjectPath, subject);
}

/// Where the picked subject lives.
const currentSubjectPath = '${Paths.prefs}/current_subject';

/// Key for the last `stats` pulled (Progress).
const kStatsCacheKey = 'stats';

/// Key for the last `stats.today` pulled (Home, the session header).
const kTodayCacheKey = 'session.stats_today';

/// `stats`, or null when the worker has not written it yet. Offline-first:
/// each answer is kept in [kv], and an unreachable database answers with
/// the last one kept.
Future<Stats?> fetchStats(RtdbClient client, KvStore kv) async {
  final Object? raw;
  try {
    raw = await client.get(Paths.stats);
  } on RtdbError catch (error) {
    log('stats unreachable; last kept copy', level: 900, error: error);
    return await _parseKept(kv, kStatsCacheKey, Stats.fromJson);
  }
  await keepNode(kv, kStatsCacheKey, raw);
  return raw == null ? null : Stats.fromJson(asJson(raw, 'stats'));
}

/// Keeps [raw] under [key], or forgets the key when the node is gone.
Future<void> keepNode(KvStore kv, String key, Object? raw) =>
    raw == null ? kv.remove(key) : kv.set(key, jsonEncode(raw));

/// The last `stats.today` kept by [keepNode], or null (none, or unreadable).
Future<Today?> keptToday(KvStore kv) =>
    _parseKept(kv, kTodayCacheKey, Today.fromJson);

Future<T?> _parseKept<T>(KvStore kv, String key, T Function(Json) parse) async {
  final kept = await kv.get(key);
  if (kept == null) return null;
  try {
    return parse(asJson(jsonDecode(kept), key));
  } on FormatException catch (error) {
    // A copy from an older build that no longer parses: show nothing
    // rather than fail the screen; the next sync overwrites it.
    log('kept $key unreadable', level: 900, error: error);
    return null;
  }
}
