/// What the coach screens keep on this install: the code per problem and
/// language, the chosen language and a copy of the thread.
library;

import 'dart:convert';

import 'package:tutor/coach/coach_models.dart';
import 'package:tutor/sql/lesson_models.dart';
import 'package:tutor/sql/sql_models.dart';
import 'package:tutor/storage/kv_store.dart';

/// Drafts of one install.
class CoachDrafts {
  /// Creates the drafts over `kv`.
  const new(this.kv);

  /// The store.
  final KvStore kv;

  /// The saved code of `slug` in `lang`; null = never edited (the starter
  /// code goes in).
  Future<String?> code(String slug, String lang) =>
      kv.get('coach.code.$slug.$lang');

  /// Saves the code.
  Future<void> saveCode(String slug, String lang, String text) =>
      kv.set('coach.code.$slug.$lang', text);

  /// The language chosen for `slug` (default Python 3).
  Future<String> lang(String slug) async {
    final saved = await kv.get('coach.lang.$slug');
    return coachLangs.containsKey(saved) ? saved! : defaultCoachLang;
  }

  /// Saves the language of `slug`.
  Future<void> saveLang(String slug, String lang) =>
      kv.set('coach.lang.$slug', lang);

  /// The stored thread of `session` (empty if none or damaged).
  Future<List<Bubble>> thread(String session) async {
    final raw = await kv.get('coach.thread.$session');
    if (raw == null) return const [];
    try {
      final list = jsonDecode(raw);
      if (list is! List) return const [];
      return [
        for (final e in list)
          if (e is Map<String, dynamic>) parseBubble(e),
      ];
    } on FormatException {
      return const [];
    }
  }

  /// Saves the thread of `session`.
  Future<void> saveThread(String session, List<Bubble> thread) => kv.set(
    'coach.thread.$session',
    jsonEncode([
      for (final b in thread)
        {
          'mine': b.mine,
          'md': b.md,
          if (b.grid case final SqlTable g)
            'grid': {'columns': g.columns, 'rows': g.rows},
        },
    ]),
  );
}
