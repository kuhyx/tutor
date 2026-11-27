// Offline-first gate (rules/offline-first): every database read in lib/
// keeps what it pulls on this install and shows that copy when the
// database cannot answer. A read in a file not listed here fails this test
// until its kept copy (and a test that reads it back offline) exists.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// File -> read calls it makes, each backed by a kept copy, and the test
/// that reads that copy back offline.
const _reviewed = {
  // HistoryStore; test/history/
  'lib/history/history.dart': 3,
  // kCatalogCacheKey; test/home/catalog_test.dart
  'lib/home/catalog.dart': 1,
  // catalog, prefs, today kept; test/home/home_offline_test.dart. `meta`
  // and `live` are live-only: offline Home skips the schema check and has
  // no live session to show.
  'lib/home/home_loader.dart': 7,
  // kStatsCacheKey; test/home/catalog_test.dart
  'lib/home/remote_bits.dart': 1,
  // the event log itself is the kept copy; test/log/
  'lib/log/event_log.dart': 2,
  // kTodayCacheKey; test/session/today_header_test.dart
  'lib/session/today_header.dart': 1,
};

final _read = RegExp(r'\bclient\.(get|keys)\(');

/// File -> stream listens it opens, as for [_reviewed].
const _reviewedListens = {
  // `live` + the session: kept by session_kept.dart;
  // test/session/session_feed_kept_test.dart
  'lib/session/session_feed.dart': 2,
  // live-only: which workers are up now; a kept copy would claim a dead
  // worker is alive
  'lib/presence/presence_watcher.dart': 1,
};

final _listen = RegExp(r'stream\.listen\(');

Map<String, int> _count(RegExp pattern) {
  final found = <String, int>{};
  for (final f in Directory('lib').listSync(recursive: true)) {
    if (f is! File || !f.path.endsWith('.dart')) continue;
    final n = pattern.allMatches(f.readAsStringSync()).length;
    if (n > 0) found[f.path] = n;
  }
  return found;
}

void main() {
  test('every database read is on the reviewed offline-first list', () {
    expect(_count(_read), _reviewed);
  });

  test('every stream listen is on the reviewed offline-first list', () {
    expect(_count(_listen), _reviewedListens);
  });
}
