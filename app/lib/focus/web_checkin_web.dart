/// The web half of `web_checkin.dart`: a browser `Notification` that asks
/// for a check-in while the focus timer runs on the PC. It is icon-only
/// (textgate): an empty title, no body, the app icon.
///
/// The screen's own prompt (focus screen) is the primary ask; this adds the
/// system notification so a check-in is still possible with the tab behind
/// another window. Clicking it only brings the app to the Focus screen, where
/// the check-in is a graded card (or the old tap). Permission is requested
/// when the timer arms the first prompt (that call follows the Start tap, so
/// Chrome allows the dialog);
/// when it is denied or missing the notifier does nothing and the in-app
/// prompt carries on alone.
library;

import 'dart:async';
import 'dart:js_interop';
import 'dart:js_interop_unsafe';

import 'package:tutor/focus/checkin_notifier.dart';

@JS('Notification')
extension type _Notification._(JSObject _) implements JSObject {
  external new(String title, _Options options);

  external static String get permission;

  external static JSPromise<JSString> requestPermission();

  external JSFunction? get onclick;

  external set onclick(JSFunction? handler);

  external void close();
}

@JS()
@anonymous
extension type _Options._(JSObject _) implements JSObject {
  external new({String icon, String tag, bool requireInteraction});
}

/// The browser notifier for the focus timer.
FocusCheckinNotifier createWebCheckinNotifier() => _WebCheckinNotifier();

bool get _supported => globalContext.has('Notification');

class _WebCheckinNotifier implements FocusCheckinNotifier {
  final _taps = StreamController<int>.broadcast();
  Timer? _armed;
  _Notification? _shown;

  @override
  Future<void> schedule(Duration after) async {
    await cancel();
    if (!_supported) return;
    if (_Notification.permission == 'default') {
      // Best effort: an unanswered or denied dialog leaves only the in-app
      // prompt, which is already on screen.
      unawaited(_Notification.requestPermission().toDart.then((_) {}));
    }
    _armed = Timer(after, _show);
  }

  void _show() {
    if (_Notification.permission != 'granted') return;
    final note = _Notification(
      '',
      _Options(
        icon: 'icons/Icon-192.png',
        tag: 'focus-checkin',
        requireInteraction: true,
      ),
    );
    note.onclick = (() {
      _taps.add(DateTime.now().millisecondsSinceEpoch);
      note.close();
      globalContext.callMethod<JSAny?>('focus'.toJS);
    }).toJS;
    _shown = note;
  }

  @override
  Future<void> cancel() async {
    _armed?.cancel();
    _armed = null;
    _shown?.close();
    _shown = null;
  }

  @override
  Stream<int> get confirmations => _taps.stream;

  @override
  Future<List<int>> takePending() async => const <int>[];
}
