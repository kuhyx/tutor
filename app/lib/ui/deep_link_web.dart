/// The web half of `deep_link.dart`.
library;

import 'dart:async';
import 'dart:js_interop';

import 'package:tutor/ui/deep_link.dart' show handedOffer;

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

extension type _Message._(JSObject _) implements JSObject {
  external JSAny? get data;
}

@JS('BroadcastChannel')
extension type _Channel._(JSObject _) implements JSObject {
  external new(String name);

  external void postMessage(JSAny? message);

  external JSFunction? get onmessage;

  external set onmessage(JSFunction? handler);
}

@JS('focus')
external void _focusWindow();

/// Drops the route from the address bar once it is opened, so a reload (F5
/// after a deliberate Stop) does not start the timer again.
void forgetDeepLink() =>
    _history.replaceState(null, '', '${_location.pathname}${_location.search}');

_Channel? _windows;
final _handed = StreamController<String>.broadcast();

/// Routes a later window handed to this one ([joinWindows]).
Stream<String> get handedRoutes => _handed.stream;

/// Every window joins at start, to take a later `/learn/...` or
/// `/rework/...` launch.
///
/// Chrome hands each `tutor --route` launch to the browser already running
/// the profile, which opens a NEW `--app` window. A page may close itself
/// only while its history has one entry, which a used window never has; so
/// the new window, before Flutter boots (`web/index.html`), offers its route
/// here (`learn <route>`) and closes itself once a window answers
/// (`took <route>`). Only a window whose app listens ([handedRoutes]) takes
/// it; otherwise the new window boots as usual. Other origins (a sandbox on
/// another port) never hear it.
void joinWindows() {
  _windows ??= _Channel('tutor-window')
    ..onmessage = ((_Message message) {
      final offer = message.data.dartify();
      if (offer is! String || !handedOffer(offer)) return;
      if (!_handed.hasListener) return;
      final route = offer.substring('learn '.length);
      _windows?.postMessage('took $route'.toJS);
      _focusWindow(); // best effort: the browser may keep it where it is
      _handed.add(route);
    }).toJS;
}
