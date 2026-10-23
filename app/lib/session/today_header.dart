/// The Session header: the DAY's totals from `stats.today` (curriculum §7),
/// this session's own minutes second. A new card is a new session, so a
/// per-session counter fell to "Active 0 min · credited 0" right after Next
/// card although the day's credit stood (kuhy, 2026-10-12).
library;

import 'dart:async';
import 'dart:developer';

import 'package:flutter/foundation.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/sync/rev_watcher.dart';
import 'package:tutor/sync/rtdb_client.dart';

/// `stats.today`, read on [start] and again on every `rev.stats` move.
class TodayFeed {
  /// Creates the feed.
  new({required this.client, required this.rev});

  /// REST client.
  final RtdbClient client;

  /// The shared `rev` listen.
  final RevWatcher rev;

  /// Latest `stats.today` (null until read, or when there is none).
  final ValueNotifier<Today?> today = ValueNotifier(null);

  StreamSubscription<int>? _sub;

  /// Reads now and follows the moves (idempotent).
  void start() {
    if (_sub != null) return;
    _sub = rev.statsChanges.listen((_) => unawaited(load()));
    unawaited(load());
  }

  /// One read; a failure keeps the last value.
  Future<void> load() async {
    try {
      final raw = await client.get('${Paths.stats}/today');
      today.value = raw == null ? null : Today.fromJson(asJson(raw, 'today'));
    } on Object catch (error) {
      // `on Object`: offline or malformed, the header keeps what it had.
      log('stats.today unavailable', level: 900, error: error);
    }
  }

  /// Stops following and releases the notifier.
  Future<void> dispose() async {
    await _sub?.cancel();
    _sub = null;
    today.dispose();
  }
}

/// The header's two lines: the day first, then this session.
(String, String) headerLines(
  Today? today, {
  required double activeSeconds,
  required int sessionCredited,
}) {
  final session =
      'This card: ${(activeSeconds / 60).floor()} min'
      ' · credited $sessionCredited';
  if (today == null) return ('Today: …', session);
  final active = today.activeMinutes;
  final note = bankNote(today);
  return (
    'Today: ${active == null ? '' : '$active min active · '}'
        'credited ${today.creditedMinutes}/${today.target} min'
        '${note == null ? '' : ' · $note'}',
    session,
  );
}

/// "Banked N min · prepaid M": the carry-over bank (DOCS-contract-carry.md),
/// or null when both are 0 or the worker predates it.
String? bankNote(Today today) {
  final banked = today.banked ?? 0;
  final prepaid = today.prepaid ?? 0;
  if (banked <= 0 && prepaid <= 0) return null;
  return 'Banked $banked min · prepaid $prepaid';
}
