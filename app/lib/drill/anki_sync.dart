/// "Sync Anki & credit": asks AnkiDroid to sync (Android only, one intent
/// through a tiny MethodChannel), then polls `anki_status` until the day's
/// credited Anki minutes rise or the wait runs out.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';

/// Fires AnkiDroid's `com.ichi2.anki.DO_SYNC` intent.
abstract interface class AnkiLauncher {
  /// Whether this platform can launch AnkiDroid at all.
  bool get supported;

  /// Sends the intent; false when AnkiDroid is not installed or refused.
  Future<bool> sync();
}

/// The Android implementation (`MainActivity.kt` answers `sync`).
class ChannelAnkiLauncher implements AnkiLauncher {
  /// Creates the launcher; tests pass their own [platform].
  new({this.platform});

  /// The platform check; default: Android, never the web build (a phone
  /// browser also reports `android` there, but has no channel).
  final bool Function()? platform;

  static const _channel = MethodChannel('com.kuhy.tutor/anki');

  @override
  bool get supported =>
      platform?.call() ??
      (!kIsWeb && defaultTargetPlatform == TargetPlatform.android);

  @override
  Future<bool> sync() async {
    try {
      return await _channel.invokeMethod<bool>('sync') ?? false;
    } on PlatformException {
      return false;
    }
  }
}

/// One sync-and-wait run at a time.
class AnkiSync extends ChangeNotifier {
  /// Creates the sync; [interval]/[timeout]/[now] are injectable for tests.
  new({
    required RequestRelay relay,
    required this.launcher,
    this.interval = const Duration(seconds: 1),
    this.timeout = const Duration(seconds: 60),
    DateTime Function()? now,
  }) : _runner = RequestRunner(relay),
       _now = now ?? DateTime.now;

  /// The intent route.
  final AnkiLauncher launcher;

  /// Gap between polls.
  final Duration interval;

  /// Longest wait for the credit to rise.
  final Duration timeout;

  final RequestRunner _runner;
  final DateTime Function() _now;
  bool _disposed = false;

  /// Whether a run is going.
  bool running = false;

  /// The result line ("+3 min from Anki", or why not); null before a run.
  String? message;

  /// Set when the PC says Claude is out.
  Unavailable? unavailable;

  /// Runs once: baseline, intent, then polls.
  Future<void> run() async {
    if (running) return;
    running = true;
    _say('Syncing AnkiDroid...');
    final base = await _credited();
    if (base == null) {
      _end('The PC did not answer.');
    } else if (!await launcher.sync()) {
      _end('AnkiDroid did not start a sync. Is it installed?');
    } else {
      _end(await _wait(base));
    }
  }

  Future<String> _wait(int base) async {
    final deadline = _now().add(timeout);
    while (!_disposed && _now().isBefore(deadline)) {
      await Future<void>.delayed(interval);
      final now = await _credited();
      if (now != null && now > base) return '+${now - base} min from Anki';
    }
    return 'No new credit from Anki yet. AnkiDroid syncs at most every 2 min.';
  }

  Future<int?> _credited() async {
    final status = await _runner.run(RequestBody.ankiStatus());
    if (status is! RelayDone) return null;
    try {
      final s = AnkiStatus.fromJson(status.data);
      unavailable = s.unavailable ?? unavailable;
      return s.creditedTodayMin;
    } on FormatException {
      return null;
    }
  }

  void _end(String text) {
    running = false;
    _say(text);
  }

  void _say(String text) {
    message = text;
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    unawaited(_runner.dispose());
    super.dispose();
  }
}
