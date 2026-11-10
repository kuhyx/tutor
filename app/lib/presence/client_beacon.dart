/// Writes `presence/clients/{dev}` (DOCS-contract §3, §5): platform, app
/// version and the server time, on start and on every resume.
///
/// The worker's phone-prep check reads the newest `seen` of an `android`
/// client; without this write the check can never pass
/// (DOCS-contract-focus.md, "Phone-prep check").
library;

import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:tutor/config/app_version.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/model/root.dart';
import 'package:tutor/sync/rtdb_client.dart';

/// Keeps this install's presence record fresh while it is in use.
class ClientBeacon with WidgetsBindingObserver {
  /// Creates the beacon; [platform] is `android` or `web`; tests inject
  /// `binding` to drive the lifecycle.
  new({
    required this.client,
    required this.dev,
    required this.platform,
    this._binding,
  });

  /// REST client.
  final RtdbClient client;

  /// This install's device id.
  final String dev;

  /// `android` or `web`.
  final String platform;

  final WidgetsBinding? _binding;
  bool _started = false;

  /// The last failed write (null after a good one): the record is only
  /// advisory, so a failure is shown by whoever listens, never thrown.
  final ValueNotifier<Object?> lastError = ValueNotifier(null);

  WidgetsBinding get _b => _binding ?? WidgetsBinding.instance;

  /// Writes now and again on each resume (idempotent).
  void start() {
    if (_started) return;
    _started = true;
    _b.addObserver(this);
    unawaited(write());
  }

  /// Stops the resume writes.
  void stop() {
    if (!_started) return;
    _started = false;
    _b.removeObserver(this);
  }

  /// PUTs the record; never throws.
  Future<void> write() async {
    try {
      await client.put(
        Paths.client(dev),
        ClientPresence(platform: platform, app: appVersion).toJson(),
      );
      lastError.value = null;
    } on Object catch (error, stack) {
      lastError.value = error;
      debugPrint('presence/clients write failed: $error\n$stack');
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) unawaited(write());
  }
}
