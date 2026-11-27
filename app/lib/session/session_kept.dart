/// The kept copy of the last session streamed, per subject (offline-first:
/// a cold start with no network shows it before the stream answers). Only
/// `meta` and `msgs` are kept: `progress` is a live trace that means
/// nothing once the turn it belongs to is gone.
library;

import 'dart:convert';
import 'dart:developer';

import 'package:tutor/model/ids.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/json_tree.dart';

/// Key of the kept session for [subject] (null: any subject).
String keptSessionKey(String? subject) => 'session.last.${subject ?? '_'}';

/// The JSON kept for session [sid] whose streamed node is [tree].
String encodeKeptSession(String sid, Object? tree) => jsonEncode({
  'sid': sid,
  'meta': getAt(tree, 'meta'),
  'msgs': getAt(tree, 'msgs'),
});

/// Writes [encoded] under [key]; a failed write only loses the copy.
Future<void> keepSession(KvStore kv, String key, String encoded) async {
  try {
    await kv.set(key, encoded);
  } on Object catch (error) {
    // `on Object`: a storage failure must not break the live screen.
    log('session copy not kept', level: 900, error: error);
  }
}

/// The session kept under [key], or null (none, or unreadable).
Future<SessionView?> keptSession(KvStore kv, String key) async {
  final raw = await kv.get(key);
  if (raw == null) return null;
  try {
    final j = asJson(jsonDecode(raw), key);
    final sid = j['sid'];
    if (sid is! String || !isSessionId(sid)) {
      throw FormatException('kept session id "$sid"');
    }
    return SessionView(
      sid: sid,
      meta: parseMeta(j['meta']),
      messages: parseMessages(j['msgs']),
    );
  } on FormatException catch (error) {
    // A copy from an older build: show nothing; the stream rewrites it.
    log('kept session unreadable', level: 900, error: error);
    return null;
  }
}
