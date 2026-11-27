/// History (curriculum §8): `session_index` rows with their archived flag,
/// past transcripts, and archiving (`sessions/{sid}/user`, client-written).
/// Offline-first: the list and opened transcripts are kept on this install
/// and an archive lands there first, pushed by [HistoryRepo.flush].
library;

import 'dart:async';
import 'dart:developer';

import 'package:flutter/widgets.dart';
import 'package:tutor/history/history_store.dart';
import 'package:tutor/history/kept_then_live.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/model/session_index.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/retry_backoff.dart';
import 'package:tutor/sync/rtdb_client.dart';

export 'package:tutor/history/kept_then_live.dart';

/// One History row.
class HistoryEntry {
  /// Creates the entry.
  const new({required this.sid, required this.row, this.archived = false});

  /// Session id.
  final String sid;

  /// The index row.
  final SessionIndexRow row;

  /// Archived by hand (`user.archived`).
  final bool archived;

  /// Hidden from the main list: archived by hand or for having no reply.
  bool get hidden => archived || row.autoArchived;
}

/// The list split as the History screen shows it.
class HistoryLists {
  /// Creates the split.
  const new(this.shown, this.hidden);

  /// Newest first.
  final List<HistoryEntry> shown;

  /// Archived ones, newest first (behind the "Show archived" toggle).
  final List<HistoryEntry> hidden;
}

/// Splits [entries] into shown/hidden, newest first (sids sort by time).
HistoryLists splitHistory(Iterable<HistoryEntry> entries) {
  final sorted = entries.toList()..sort((a, b) => b.sid.compareTo(a.sid));
  return HistoryLists(
    [
      for (final e in sorted)
        if (!e.hidden) e,
    ],
    [
      for (final e in sorted)
        if (e.hidden) e,
    ],
  );
}

/// A past session, read once.
class Transcript {
  /// Creates the transcript.
  const new({required this.view, this.archived = false});

  /// Meta and messages.
  final SessionView view;

  /// Archived by hand.
  final bool archived;
}

/// Loads History data: live from the database, kept on this install
/// ([HistoryStore]) so it reads offline and after a restart.
class HistoryRepo {
  /// Creates the repo over [client], keeping its copy in [kv].
  new(this.client, KvStore kv) : store = HistoryStore(kv);

  /// REST client.
  final RtdbClient client;

  /// The copy on this install and the archive queue.
  final HistoryStore store;

  List<HistoryEntry> _entries(Json index, Json users, Map<String, bool> q) {
    final out = <HistoryEntry>[];
    for (final sid in index.keys.where(isSessionId)) {
      try {
        final user = users[sid];
        out.add(
          HistoryEntry(
            sid: sid,
            row: SessionIndexRow.fromJson(asJson(index[sid], sid)),
            archived:
                q[sid] ?? (user is Json && SessionUser.fromJson(user).archived),
          ),
        );
      } on FormatException catch (error) {
        log('skipping malformed history row $sid', level: 900, error: error);
      }
    }
    return out;
  }

  /// The kept list (queued archive flags applied), or null when none.
  Future<List<HistoryEntry>?> kept() async {
    final copy = await store.list();
    if (copy == null) return null;
    return _entries(copy.index, copy.users, await store.pending());
  }

  /// Every index row with its archived flag, live (queued flags are pushed
  /// first); the answer is kept. Throws [RtdbError] when unreachable.
  Future<List<HistoryEntry>> load() async {
    await flush();
    // Taken before the GETs: a flag pushed while they run may be missing
    // from their answer, so the queue as it was then still overrides it.
    final q = await store.pending();
    final node = await client.get(Paths.sessionIndex);
    final index = node is Json ? node : <String, dynamic>{};
    final sids = index.keys.where(isSessionId).toList();
    final got = await Future.wait([
      for (final sid in sids) client.get('${Paths.session(sid)}/user'),
    ]);
    final users = <String, dynamic>{
      for (final (n, sid) in sids.indexed)
        if (got[n] case final Json user) sid: user,
      for (final MapEntry(key: sid, value: a) in q.entries)
        sid: SessionUser(archived: a).toJson(),
    };
    await store.saveList(index, users);
    return _entries(index, users, q);
  }

  Transcript _transcript(String sid, Json j, Map<String, bool> q) {
    final user = j['user'];
    return Transcript(
      view: SessionView(
        sid: sid,
        meta: parseMeta(j['meta']),
        messages: parseMessages(j['msgs']),
      ),
      archived: q[sid] ?? (user is Json && SessionUser.fromJson(user).archived),
    );
  }

  /// The kept copy of [sid]'s transcript, or null when never opened.
  Future<Transcript?> keptTranscript(String sid) async {
    final j = await store.transcript(sid);
    return j == null ? null : _transcript(sid, j, await store.pending());
  }

  /// One past session's meta, messages and archived flag, live; kept.
  Future<Transcript> transcript(String sid) async {
    final q = await store.pending(); // before the GET, as in [load]
    final node = await client.get(Paths.session(sid));
    final j = <String, dynamic>{
      if (node is Json) ...node,
      if (q[sid] case final bool a) 'user': SessionUser(archived: a).toJson(),
    };
    await store.saveTranscript(sid, j);
    return _transcript(sid, j, q);
  }

  /// The kept list at once, then the live one (offline-first).
  Stream<Fetched<List<HistoryEntry>>> watch() => keptThenLive(kept, load);

  /// [sid]'s kept transcript and row at once, then the live ones.
  Stream<Fetched<(Transcript, HistoryEntry?)>> watchTranscript(String sid) {
    HistoryEntry? rowOf(List<HistoryEntry> rows) =>
        rows.where((r) => r.sid == sid).firstOrNull;
    return keptThenLive(() async {
      final t = await keptTranscript(sid);
      return t == null ? null : (t, rowOf(await kept() ?? const []));
    }, () async => (await transcript(sid), rowOf(await load())));
  }

  /// Archives or unarchives [sid] (never the live one: the caller hides
  /// the button for it, the worker ignores it anyway). Lands on this
  /// install at once, then [flush] pushes it.
  Future<void> setArchived(String sid, {required bool archived}) async {
    await store.archive(sid, archived: archived);
    unawaited(flush());
  }

  AppLifecycleListener? _lifecycle;
  late final _backoff = RetryBackoff(flush);

  /// Runs [flush] each time the app comes back on screen (the app calls
  /// this once; tests pass their [binding]).
  void flushOnShow({WidgetsBinding? binding}) {
    _lifecycle ??= AppLifecycleListener(
      binding: binding,
      onShow: () => unawaited(flush()),
    );
  }

  /// Pushes queued archive flags. A failure keeps the rest queued for the
  /// next call (every History load, Home load, app resume and archive)
  /// and for a backoff retry.
  /// Returns how many were written.
  Future<int> flush() async {
    var written = 0;
    for (final MapEntry(key: sid, value: archived)
        in (await store.pending()).entries) {
      try {
        await client.put(
          '${Paths.session(sid)}/user',
          SessionUser(archived: archived).toJson(),
        );
      } on RtdbError catch (error) {
        log('archive flag kept queued', level: 800, error: error);
        _backoff.failed();
        return written;
      }
      await store.pushed(sid, archived: archived);
      written++;
    }
    _backoff.ok();
    return written;
  }
}
