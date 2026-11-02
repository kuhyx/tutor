/// Timer events that could not reach the PC yet (DOCS-contract-focus.md,
/// "Timer events").
///
/// Every tap on the timer is one `focus_event`. A phone away from Wi-Fi, or a
/// PC that is off, must not lose minutes: [FocusEventQueue.enqueue] stores the
/// event with the CLIENT time of the tap and a rid minted then, and
/// [FocusEventQueue.flush] replays the queue in tap order with those same
/// values (the worker's done-map makes a replay harmless).
library;

import 'dart:async';
import 'dart:convert';

import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/util/ulid.dart';

const _key = 'focus_events';

/// Wire names of `focus_event.event`.
const focusEventNames = {'start', 'checkin', 'stop'};

/// One timer event waiting to be sent.
class QueuedFocusEvent {
  /// Creates the event.
  const new({
    required this.rid,
    required this.event,
    required this.ts,
    required this.platform,
  });

  /// Reads one stored entry.
  factory fromJson(Map<String, dynamic> j) => QueuedFocusEvent(
    rid: j['rid'] as String,
    event: j['event'] as String,
    ts: j['ts'] as int,
    platform: j['platform'] as String,
  );

  /// Request id, minted when the tap happened.
  final String rid;

  /// `start`, `checkin` or `stop`.
  final String event;

  /// Client time of the tap, unix ms.
  final int ts;

  /// `phone` or `pc`.
  final String platform;

  /// The stored form.
  Map<String, dynamic> toJson() => {
    'rid': rid,
    'event': event,
    'ts': ts,
    'platform': platform,
  };
}

/// What the PC said about one event.
enum FocusSendOutcome {
  /// Result landed: forget the event.
  sent,

  /// PC or network unreachable: keep it and stop (order matters).
  retry,

  /// The worker refused it for good (`bad_request`, 48 h too old): drop it.
  refused,
}

/// Sends one event under its stored rid and `ts`.
typedef FocusSender = Future<FocusSendOutcome> Function(QueuedFocusEvent event);

/// Counts of one [FocusEventQueue.flush].
class FocusFlush {
  /// Creates the counts.
  const new({required this.sent, required this.dropped, required this.left});

  /// Delivered.
  final int sent;

  /// Refused and discarded.
  final int dropped;

  /// Still queued.
  final int left;
}

/// The persisted, ordered queue.
class FocusEventQueue {
  /// Creates the queue over [_kv]; tests inject [ulid] and [now] (ms).
  new(this._kv, {UlidGenerator? ulid, int Function()? now})
    : _ulid = ulid ?? UlidGenerator(),
      _now = now ?? (() => DateTime.now().millisecondsSinceEpoch);

  final KvStore _kv;
  final UlidGenerator _ulid;
  final int Function() _now;
  Future<void> _lock = Future.value();
  Future<FocusFlush>? _flushing;
  // Rids a flush must not send yet (in memory only: after a restart the
  // process that held them is dead, so they go out).
  final Set<String> _held = {};

  /// Stores an event; [ts] defaults to now. A [hold]ing event stays queued
  /// but is not sent by [flush] until [release]d (or the process restarts).
  Future<QueuedFocusEvent> enqueue(
    String event, {
    int? ts,
    String platform = 'phone',
    bool hold = false,
  }) {
    if (!focusEventNames.contains(event)) {
      throw ArgumentError.value(event, 'event');
    }
    final e = QueuedFocusEvent(
      rid: _ulid.next(),
      event: event,
      ts: ts ?? _now(),
      platform: platform,
    );
    if (hold) _held.add(e.rid);
    return _locked(() async {
      await _write([...await pending(), e]);
      return e;
    });
  }

  /// Lets a held event go out with the next [flush].
  void release(String rid) => _held.remove(rid);

  /// Forgets a queued event that was never sent (a held one the app
  /// returned from).
  Future<void> remove(String rid) {
    _held.remove(rid);
    return _locked(() async {
      await _write([
        for (final p in await pending())
          if (p.rid != rid) p,
      ]);
    });
  }

  /// The queued events, oldest first.
  Future<List<QueuedFocusEvent>> pending() async {
    final raw = await _kv.get(_key);
    if (raw == null) return const [];
    try {
      return [
        for (final j in jsonDecode(raw) as List<dynamic>)
          QueuedFocusEvent.fromJson(j as Map<String, dynamic>),
      ];
    } on FormatException {
      return const [];
    }
  }

  /// Replays the queue through [send]; a flush already running is joined.
  /// A throwing [send] keeps the progress made and rethrows.
  Future<FocusFlush> flush(FocusSender send) {
    final running = _flushing;
    if (running != null) {
      return running.then(
        (_) => const FocusFlush(sent: 0, dropped: 0, left: 0),
      );
    }
    final run = _flush(send).whenComplete(() => _flushing = null);
    _flushing = run;
    return run;
  }

  Future<FocusFlush> _flush(FocusSender send) async {
    var sent = 0;
    var dropped = 0;
    for (final e in await pending()) {
      if (_held.contains(e.rid)) break;
      final outcome = await send(e);
      if (outcome == FocusSendOutcome.retry) break;
      await _locked(() async {
        await _write([
          for (final p in await pending())
            if (p.rid != e.rid) p,
        ]);
      });
      if (outcome == FocusSendOutcome.sent) {
        sent++;
      } else {
        dropped++;
      }
    }
    return FocusFlush(
      sent: sent,
      dropped: dropped,
      left: (await pending()).length,
    );
  }

  Future<void> _write(List<QueuedFocusEvent> events) =>
      _kv.set(_key, jsonEncode([for (final e in events) e.toJson()]));

  /// Serialises read-modify-write cycles (a tap during a flush).
  Future<T> _locked<T>(Future<T> Function() body) {
    final done = _lock.then((_) => body());
    _lock = done.then<void>((_) {}, onError: (_) {});
    return done;
  }
}
