/// Android side of `FocusCheckinNotifier`: the native `FocusCheckin` (exact
/// alarms for the prompt and the lapse cleanup, the "Still working" action and
/// the foreground timer service) in `android/.../com/kuhy/tutor/` behind one
/// method channel.
///
/// Taps are stored natively first, so one made with the app dead or the
/// screen off is never lost; `takePending` drains them.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:tutor/focus/checkin_notifier.dart';
import 'package:tutor/focus/focus_timer.dart' show lapseAfter;

/// The notifier for the phone build.
class AndroidCheckinNotifier implements FocusCheckinNotifier {
  /// Creates the notifier; tests pass a [channel] they mock.
  new({MethodChannel? channel})
    : _channel = channel ?? const MethodChannel('com.kuhy.tutor/focus') {
    _channel.setMethodCallHandler(_fromNative);
  }

  final MethodChannel _channel;
  final _taps = StreamController<int>.broadcast();
  bool _permitted = false;

  @override
  Future<void> schedule(Duration after) async {
    // Notifications are runtime-gated on Android 13+. Ask until granted; a
    // refusal still arms the timer service, the prompt just stays invisible.
    if (!_permitted) {
      _permitted =
          await _channel.invokeMethod<bool>('ensurePermission') ?? false;
    }
    await _channel.invokeMethod<void>('schedule', {
      'afterMs': after.inMilliseconds,
      'everyMs': checkinEvery.inMilliseconds,
      'lapseMs': lapseAfter.inMilliseconds,
    });
  }

  @override
  Future<void> cancel() => _channel.invokeMethod<void>('cancel');

  @override
  Stream<int> get confirmations => _taps.stream;

  @override
  Future<List<int>> takePending() async {
    final raw = await _channel.invokeMethod<List<Object?>>('takePending');
    return [for (final t in raw ?? const <Object?>[]) (t! as num).toInt()];
  }

  /// `tapped`: a tap was stored. With a listener on [confirmations] hand it
  /// over now; with none leave it for [takePending] (never drop a tap).
  Future<void> _fromNative(MethodCall call) async {
    if (call.method != 'tapped' || !_taps.hasListener) return;
    (await takePending()).forEach(_taps.add);
  }
}

/// The platform's notifier: Android gets the real one, everything else none.
FocusCheckinNotifier platformCheckinNotifier({bool? isAndroid}) {
  final android =
      isAndroid ?? (!kIsWeb && defaultTargetPlatform == TargetPlatform.android);
  return android ? AndroidCheckinNotifier() : const NoopCheckinNotifier();
}
