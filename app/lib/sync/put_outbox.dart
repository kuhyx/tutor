/// Client-written database nodes made offline-first
/// (`~/.claude/rules/offline-first.instructions.md`): [PutOutbox.put] lands
/// the write on this install at once and [PutOutbox.flush] PUTs it when the
/// database answers. Used for `prefs/current_subject` and `feedback/{fid}`;
/// History's archive flags have their own queue (`history_store.dart`).
///
/// Every queued write is an idempotent PUT to a fixed path, so a flush that
/// dies halfway is simply run again; a later write to the same path
/// replaces the queued one (last writer wins, as the contract says).
library;

import 'dart:async';
import 'dart:convert';
import 'dart:developer';

import 'package:flutter/widgets.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/retry_backoff.dart';
import 'package:tutor/sync/rtdb_client.dart';

const _key = 'outbox.puts';

/// On-disk queue of PUTs still to reach the database.
class PutOutbox {
  /// Creates the outbox over [client], kept in [kv]. A failed flush is
  /// tried again after [retryAfter], doubling up to [kMaxRetry].
  new(this.client, this.kv, {this.retryAfter = const Duration(seconds: 5)});

  /// REST client.
  final RtdbClient client;

  /// Where the queue is kept.
  final KvStore kv;

  /// First wait after a failed flush.
  final Duration retryAfter;

  late final _backoff = RetryBackoff(flush, first: retryAfter);
  Future<int>? _running;
  AppLifecycleListener? _lifecycle;

  /// Queued writes, path -> value, oldest first.
  Future<Json> pending() async {
    final raw = await kv.get(_key);
    if (raw == null) return <String, dynamic>{};
    try {
      final node = jsonDecode(raw);
      return node is Json ? node : <String, dynamic>{};
    } on FormatException {
      return <String, dynamic>{};
    }
  }

  /// The queued value for [path], or null when nothing is queued there.
  Future<Object?> pendingAt(String path) async => (await pending())[path];

  /// Queues [value] for [path] (readable at once via [pendingAt]), then
  /// starts a flush without waiting for it.
  Future<void> put(String path, Object value) async {
    final queue = (await pending())..remove(path);
    queue[path] = value;
    await kv.set(_key, jsonEncode(queue));
    unawaited(flush());
  }

  /// PUTs queued writes oldest first; returns how many reached the
  /// database. A failure keeps the rest queued and arms a backoff retry;
  /// it never throws. Concurrent calls share one run.
  Future<int> flush() => _running ??= _drain().whenComplete(() {
    _running = null;
  });

  Future<int> _drain() async {
    var written = 0;
    for (final MapEntry(key: path, :value) in (await pending()).entries) {
      try {
        await client.put(path, value);
      } on Object catch (error) {
        // `on Object`: a token failure and a network error alike mean
        // "not written yet"; the write stays queued for the next try.
        log('write kept queued', level: 800, error: error);
        _backoff.failed();
        return written;
      }
      final queue = await pending();
      if (jsonEncode(queue[path]) == jsonEncode(value)) queue.remove(path);
      await kv.set(_key, jsonEncode(queue));
      written++;
    }
    _backoff.ok();
    return written;
  }

  /// Runs [flush] each time the app comes back on screen (the app calls
  /// this once; tests pass their [binding]).
  void flushOnShow({WidgetsBinding? binding}) {
    _lifecycle ??= AppLifecycleListener(
      binding: binding,
      onShow: () => unawaited(flush()),
    );
  }

  /// Stops the retry timer and the lifecycle listener.
  void dispose() {
    _backoff.dispose();
    _lifecycle?.dispose();
  }
}
