/// The web half of `deep_link.dart`.
library;

import 'dart:js_interop';

@JS('history')
external _History get _history;

@JS('location')
external _Location get _location;

extension type _History._(JSObject _) implements JSObject {
  external void replaceState(JSAny? state, String title, String url);
}

extension type _Location._(JSObject _) implements JSObject {
  external String get pathname;

  external String get search;
}

@JS('BroadcastChannel')
extension type _Channel._(JSObject _) implements JSObject {
  external new(String name);

  external void postMessage(JSAny? message);

  external JSFunction? get onmessage;

  external set onmessage(JSFunction? handler);
}

@JS('close')
external void _closeWindow();

/// Drops the route from the address bar once it is opened, so a reload (F5
/// after a deliberate Stop) does not start the timer again.
void forgetDeepLink() =>
    _history.replaceState(null, '', '${_location.pathname}${_location.search}');

_Channel? _windows;

/// Every window joins at start: a later window's claim closes this one.
/// Chrome hands each `tutor --route` launch to the browser already running
/// the profile, which opens a NEW `--app` window; the window opened on
/// `/learn/...` ([claim]) is the one kept, as i3 maps it where the learner
/// is looking (the LeetCode lock's learn button). Other origins (a sandbox
/// on another port) never hear it.
void joinWindows({required bool claim}) {
  final channel = _windows ??= _Channel('tutor-window')
    ..onmessage = ((JSAny? _) => _closeWindow()).toJS;
  if (claim) channel.postMessage('claim'.toJS);
}
