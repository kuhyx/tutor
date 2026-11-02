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

/// Drops the route from the address bar once it is opened, so a reload (F5
/// after a deliberate Stop) does not start the timer again.
void forgetDeepLink() =>
    _history.replaceState(null, '', '${_location.pathname}${_location.search}');
