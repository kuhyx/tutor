/// What was typed for a drill (the SQL, the prediction grid), kept in the
/// per-install store so leaving the screen or the app loses nothing.
library;

import 'dart:convert';

import 'package:tutor/sql/sql_models.dart';
import 'package:tutor/storage/kv_store.dart';

/// Drafts of one install.
class SqlDrafts {
  /// Creates the drafts over [kv].
  const new(this.kv);

  /// The store.
  final KvStore kv;

  /// The saved SQL of drill [id] (empty if none).
  Future<String> sql(String id) async => await kv.get('sql.sql.$id') ?? '';

  /// Saves the SQL of drill [id].
  Future<void> saveSql(String id, String text) => kv.set('sql.sql.$id', text);

  /// The lesson id saved for [topic] (null if none).
  Future<String?> lesson(String topic) => kv.get('sql.lesson.$topic');

  /// Saves the lesson id of [topic].
  Future<void> saveLesson(String topic, String id) =>
      kv.set('sql.lesson.$topic', id);

  /// Forgets the lesson of [topic].
  Future<void> forgetLesson(String topic) => kv.remove('sql.lesson.$topic');

  /// The saved prediction grid of drill [id] (empty if none or damaged).
  Future<Grid> grid(String id) async {
    final raw = await kv.get('sql.grid.$id');
    if (raw == null) return const [];
    try {
      final rows = jsonDecode(raw);
      if (rows is! List) return const [];
      return [
        for (final r in rows)
          if (r is List) [for (final c in r) '$c'],
      ];
    } on FormatException {
      return const [];
    }
  }

  /// Saves the prediction grid of drill [id].
  Future<void> saveGrid(String id, Grid grid) =>
      kv.set('sql.grid.$id', jsonEncode(grid));
}
