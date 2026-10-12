/// Subjects with their plan and cards, from Home's catalog cache (refreshed
/// when `rev.catalog` moves) or fetched fresh for one subject (the Plan and
/// Editor screens after a request lands).
library;

import 'dart:convert';
import 'dart:developer';

import 'package:tutor/model/card.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/rtdb_client.dart';

/// kv key of the catalog cache (`{"rev":n,"subjects":{...}}`).
const kCatalogCacheKey = 'catalog.cache';

/// One subject, parsed.
class SubjectData {
  /// Creates the record.
  const new({
    required this.id,
    required this.meta,
    this.plan,
    this.cards = const {},
    this.concepts = const [],
  });

  /// Subject id.
  final String id;

  /// `meta`.
  final SubjectMeta meta;

  /// `plan`, null while drafting.
  final Plan? plan;

  /// Cards by id.
  final Map<String, StudyCard> cards;

  /// Mastered concepts, oldest first.
  final List<Concept> concepts;

  /// Cards of module [module], in teaching order.
  List<MapEntry<String, StudyCard>> cardsOf(String module) =>
      cards.entries.where((e) => e.value.module == module).toList()
        ..sort((a, b) => a.value.order.compareTo(b.value.order));
}

/// Parses `subjects/{id}`; null when it has no (valid) meta yet.
SubjectData? parseSubject(String id, Object? node) {
  if (node is! Map<String, dynamic>) return null;
  try {
    final meta = objOr(node, 'meta');
    if (meta == null) return null;
    final plan = objOr(node, 'plan');
    final cards = <String, StudyCard>{};
    for (final MapEntry(:key, :value) in (objOr(node, 'cards') ?? {}).entries) {
      try {
        cards[key] = StudyCard.fromJson(value);
      } on FormatException catch (error) {
        log('skipping malformed card $id/$key', level: 900, error: error);
      }
    }
    return SubjectData(
      id: id,
      meta: SubjectMeta.fromJson(meta),
      plan: plan == null ? null : Plan.fromJson(plan),
      cards: cards,
      concepts: listOf(node, 'concepts', Concept.fromJson),
    );
  } on FormatException catch (error) {
    log('skipping malformed subject $id', level: 900, error: error);
    return null;
  }
}

/// Reads and refreshes subjects.
class Catalog {
  /// Creates the catalog.
  new({required this.client, required this.kv});

  /// REST client.
  final RtdbClient client;

  /// Cache store (shared with Home).
  final KvStore kv;

  Future<Json> _cache() async {
    final raw = await kv.get(kCatalogCacheKey);
    return raw == null
        ? {'rev': -1, 'subjects': <String, dynamic>{}}
        : asJson(jsonDecode(raw));
  }

  /// Every cached subject, by id.
  Future<Map<String, SubjectData>> cached() async {
    final subjects = objOr(await _cache(), 'subjects') ?? const {};
    return {
      for (final MapEntry(:key, :value) in subjects.entries)
        key: ?parseSubject(key, value),
    };
  }

  /// Fetches subject [id] fresh and updates its cache entry (the catalog
  /// rev is kept, so Home still refetches when `rev.catalog` moves).
  Future<SubjectData?> fetch(String id) async {
    if (!isSlug(id)) return null;
    final node = await client.get(Paths.subject(id));
    final cache = await _cache();
    final subjects = {...?objOr(cache, 'subjects'), id: node};
    await kv.set(
      kCatalogCacheKey,
      jsonEncode({...cache, 'subjects': subjects}),
    );
    return parseSubject(id, node);
  }
}
