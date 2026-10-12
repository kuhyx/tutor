/// History (curriculum §8): `session_index` rows with their archived flag,
/// past transcripts, and archiving (`sessions/{sid}/user`, client-written).
library;

import 'dart:developer';

import 'package:tutor/model/ids.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/model/session_index.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/sync/rtdb_client.dart';

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

/// Loads History data.
class HistoryRepo {
  /// Creates the repo.
  new(this.client);

  /// REST client.
  final RtdbClient client;

  /// Every index row with its archived flag.
  Future<List<HistoryEntry>> load() async {
    final index = await client.get(Paths.sessionIndex);
    if (index is! Map<String, dynamic>) return const [];
    final sids = index.keys.where(isSessionId).toList();
    final users = await Future.wait([
      for (final sid in sids) client.get('${Paths.session(sid)}/user'),
    ]);
    final out = <HistoryEntry>[];
    for (final (n, sid) in sids.indexed) {
      try {
        final user = users[n];
        out.add(
          HistoryEntry(
            sid: sid,
            row: SessionIndexRow.fromJson(asJson(index[sid], sid)),
            archived: user is Json && SessionUser.fromJson(user).archived,
          ),
        );
      } on FormatException catch (error) {
        log('skipping malformed history row $sid', level: 900, error: error);
      }
    }
    return out;
  }

  /// One past session's meta, messages and archived flag.
  Future<Transcript> transcript(String sid) async {
    final node = await client.get(Paths.session(sid));
    final j = node is Json ? node : const <String, dynamic>{};
    final user = j['user'];
    return Transcript(
      view: SessionView(
        sid: sid,
        meta: parseMeta(j['meta']),
        messages: parseMessages(j['msgs']),
      ),
      archived: user is Json && SessionUser.fromJson(user).archived,
    );
  }

  /// Archives or unarchives [sid] (never the live one: the caller hides
  /// the button for it, the worker ignores it anyway).
  Future<void> setArchived(String sid, {required bool archived}) => client.put(
    '${Paths.session(sid)}/user',
    SessionUser(archived: archived).toJson(),
  );
}
