/// What Home shows: subjects, due-review count, today's counters, and
/// whether this client may talk to this database at all (schema gate).
///
/// The catalog (`subjects/{s}`) is fetched only when `rev.catalog` moved
/// (DOCS-contract §9) and cached, so Home and the review count work offline.
library;

import 'dart:convert';
import 'dart:developer';

import 'package:tutor/home/catalog.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/model/card.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/model/root.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/rtdb_client.dart';

/// Schema version this client understands (DOCS-contract §3 `meta`).
const kSchema = 1;

/// This client's version for `min_client`.
const kClientVersion = 1;

/// One subject on Home.
class SubjectEntry {
  /// Creates the entry.
  const new(this.id, this.meta, [this.data]);

  /// Subject id.
  final String id;

  /// Its meta.
  final SubjectMeta meta;

  /// Plan, cards and concepts (null only when they failed to parse).
  final SubjectData? data;
}

/// Home's data.
class HomeSnapshot {
  /// Creates the snapshot.
  const new({
    required this.subjects,
    required this.due,
    required this.offline,
    this.today,
    this.currentSubject,
    this.live,
    this.toReview = const {},
  });

  /// Subject id -> its first module that is done but not reviewed.
  final Map<String, ModuleRef> toReview;

  /// Subjects, by title.
  final List<SubjectEntry> subjects;

  /// Cards due for review now, all subjects.
  final int due;

  /// Built from the cache because the database was unreachable.
  final bool offline;

  /// `stats.today`, when reachable.
  final Today? today;

  /// `prefs.current_subject`, when reachable.
  final String? currentSubject;

  /// The live session, when reachable and one is live.
  final Live? live;
}

/// Thrown when the database's schema is newer than this client.
class UnsupportedSchema implements Exception {
  /// Creates the error.
  const new(this.meta);

  /// What the database announced.
  final SchemaMeta meta;

  @override
  String toString() =>
      'This app is too old for the tutor data (schema ${meta.schema}, '
      'needs client ${meta.minClient}). Update the app.';
}

const String _cacheKey = kCatalogCacheKey;

/// Loads [HomeSnapshot]s.
class HomeLoader {
  /// Creates the loader.
  new({
    required this.client,
    required this.kv,
    required this.events,
    DateTime Function()? now,
  }) : _now = now ?? DateTime.now;

  /// REST client.
  final RtdbClient client;

  /// Catalog cache.
  final KvStore kv;

  /// Event log (flushed and pulled on every load).
  final EventLog events;
  final DateTime Function() _now;

  /// Loads Home. Throws [UnsupportedSchema]; network failures fall back
  /// to the cached catalog (and rethrow only when there is none).
  Future<HomeSnapshot> load() async {
    Json catalog;
    Today? today;
    String? current;
    Live? live;
    var offline = false;
    try {
      final meta = await client.get(Paths.meta);
      if (meta != null) {
        final m = SchemaMeta.fromJson(asJson(meta, 'meta'));
        if (!m.allows(knownSchema: kSchema, clientVersion: kClientVersion)) {
          throw UnsupportedSchema(m);
        }
      }
      catalog = await _catalog();
      final t = await client.get('${Paths.stats}/today');
      today = t == null ? null : Today.fromJson(asJson(t, 'today'));
      final p = await client.get(Paths.prefs);
      current = p == null ? null : Prefs.fromJson(asJson(p)).currentSubject;
      final l = await client.get(Paths.live);
      live = l == null ? null : Live.fromJson(asJson(l, 'live'));
    } on RtdbError catch (error) {
      final cached = await kv.get(_cacheKey);
      if (cached == null) rethrow;
      log('database unreachable; Home from cache', level: 900, error: error);
      catalog = asJson(jsonDecode(cached));
      offline = true;
    }
    await _syncLog(offline: offline);
    final snap = await _build(
      asJson(catalog['subjects'] ?? <String, dynamic>{}),
      today,
      offline,
    );
    return HomeSnapshot(
      subjects: snap.subjects,
      due: snap.due,
      offline: offline,
      today: today,
      currentSubject: current,
      live: live,
      toReview: snap.toReview,
    );
  }

  Future<Json> _catalog() async {
    final revRaw = await client.get(Paths.rev);
    final rev = revRaw == null ? 0 : Revs.fromJson(asJson(revRaw)).catalog;
    final cachedRaw = await kv.get(_cacheKey);
    if (cachedRaw != null) {
      final cached = asJson(jsonDecode(cachedRaw));
      if (cached['rev'] == rev) return cached;
    }
    final subjects = <String, dynamic>{};
    for (final id in (await client.keys(Paths.subjects)).where(isSlug)) {
      subjects[id] = await client.get(Paths.subject(id));
    }
    final catalog = {'rev': rev, 'subjects': subjects};
    await kv.set(_cacheKey, jsonEncode(catalog));
    return catalog;
  }

  Future<void> _syncLog({required bool offline}) async {
    if (offline) return;
    try {
      await events.flush();
      await events.pull();
    } on Object catch (error) {
      // `on Object`: a half-synced log is fine (it resumes next time); the
      // due count then comes from what is local.
      log(
        'event log sync failed; using local events',
        level: 900,
        error: error,
      );
    }
  }

  Future<HomeSnapshot> _build(Json subjects, Today? today, bool offline) async {
    final entries = <SubjectEntry>[];
    final cards = <String, CardInfo>{};
    for (final MapEntry(key: id, value: raw) in subjects.entries) {
      final s = asJson(raw, id);
      final meta = objOr(s, 'meta');
      if (meta == null) continue; // being created
      entries.add(
        SubjectEntry(id, SubjectMeta.fromJson(meta), parseSubject(id, s)),
      );
      for (final MapEntry(key: cid, value: c) in mapOf(
        s,
        'cards',
        (v) => v,
      ).entries) {
        final card = StudyCard.fromJson(c);
        cards['$id/$cid'] = CardInfo(rev: card.rev, suspended: card.suspended);
      }
    }
    entries.sort((a, b) => a.meta.title.compareTo(b.meta.title));
    final folded = fold(await events.all(), cards);
    final now = _now().toUtc();
    final due = reviewQueue(folded, cards, now).length;
    return HomeSnapshot(
      subjects: entries,
      due: due,
      offline: offline,
      today: today,
      toReview: {
        for (final e in entries)
          if (e.data case final d?)
            e.id: ?moduleToReview(d, subjectProgress(d, folded, now)),
      },
    );
  }
}
