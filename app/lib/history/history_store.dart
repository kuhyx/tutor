/// What History keeps on this install (offline-first,
/// `~/.claude/rules/offline-first.instructions.md`): the last pulled list,
/// every opened transcript and the archive flags still to be pushed.
///
/// Transcripts share a character [HistoryStore.budget]; past it the
/// oldest saved ones go first (the phone's preferences file is read whole).
library;

import 'dart:convert';

import 'package:tutor/model/json.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/storage/kv_store.dart';

/// Characters of transcript JSON kept on disk across all sessions.
const kTranscriptBudget = 2000000;

const _listKey = 'history.list';
const _queueKey = 'history.archive.queue';
// Sid -> `[size, savedSeq]`, oldest evicted first.
const _indexKey = 'history.transcripts';
String _transcriptKey(String sid) => 'history.transcript.$sid';

/// The last list as pulled: the `session_index` node and each sid's `user`.
typedef KeptList = ({Json index, Json users});

/// History's local copy and archive queue.
class HistoryStore {
  /// Creates the store over [kv].
  new(this.kv, {this.budget = kTranscriptBudget});

  /// The store.
  final KvStore kv;

  /// Characters of transcript JSON kept at most.
  final int budget;

  Future<Json?> _json(String key) async {
    final raw = await kv.get(key);
    if (raw == null) return null;
    try {
      final node = jsonDecode(raw);
      return node is Json ? node : null;
    } on FormatException {
      return null;
    }
  }

  Json _obj(Object? v) => v is Json ? v : <String, dynamic>{};

  /// The last list, or null when none was kept.
  Future<KeptList?> list() async {
    final j = await _json(_listKey);
    return j == null
        ? null
        : (index: _obj(j['index']), users: _obj(j['users']));
  }

  /// Keeps [index] and [users] as the last list.
  Future<void> saveList(Json index, Json users) =>
      kv.set(_listKey, jsonEncode({'index': index, 'users': users}));

  Future<Map<String, List<int>>> _index() async => {
    for (final MapEntry(:key, :value)
        in (await _json(_indexKey) ?? const <String, dynamic>{}).entries)
      if (value is List && value.length == 2 && value.every((v) => v is int))
        key: value.cast<int>(),
  };

  /// The last `sessions/{sid}` node, or null when none was kept.
  Future<Json?> transcript(String sid) async =>
      (await _index()).containsKey(sid)
      ? await _json(_transcriptKey(sid))
      : null;

  /// Keeps [node] as [sid]'s transcript, dropping the oldest past [budget].
  Future<void> saveTranscript(String sid, Json node) async {
    final raw = jsonEncode(node);
    if (raw.length > budget) return;
    final index = (await _index())..remove(sid);
    final seq = index.values.fold(0, (m, r) => r[1] > m ? r[1] : m) + 1;
    var used = index.values.fold(0, (s, r) => s + r[0]) + raw.length;
    final oldest = index.keys.toList()
      ..sort((a, b) => index[a]![1].compareTo(index[b]![1]));
    for (final gone in oldest) {
      if (used <= budget) break;
      used -= index.remove(gone)![0];
      await kv.remove(_transcriptKey(gone));
    }
    index[sid] = [raw.length, seq];
    await kv.set(_transcriptKey(sid), raw);
    await kv.set(_indexKey, jsonEncode(index));
  }

  /// Archive flags not yet written to the database.
  Future<Map<String, bool>> pending() async => {
    for (final MapEntry(:key, :value)
        in (await _json(_queueKey) ?? const <String, dynamic>{}).entries)
      if (value is bool) key: value,
  };

  /// Records [sid]'s flag locally: queued, and folded into the kept list
  /// and transcript so it reads back at once, offline or after a restart.
  Future<void> archive(String sid, {required bool archived}) async {
    final queue = await pending();
    queue[sid] = archived;
    await kv.set(_queueKey, jsonEncode(queue));
    final user = SessionUser(archived: archived).toJson();
    if (await list() case final kept?) {
      await saveList(kept.index, {...kept.users, sid: user});
    }
    if (await transcript(sid) case final node?) {
      await saveTranscript(sid, {...node, 'user': user});
    }
  }

  /// Drops [sid] from the queue once [archived] reached the database
  /// (unless a newer flag was queued meanwhile).
  Future<void> pushed(String sid, {required bool archived}) async {
    final queue = await pending();
    if (queue[sid] != archived) return;
    queue.remove(sid);
    await kv.set(_queueKey, jsonEncode(queue));
  }
}
