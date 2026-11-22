/// Deep links of the desktop (web) build: `…/app/#/focus?start=1` opens the
/// focus screen (`ui/nav.dart` routes), written by `focus_project.open`.
library;

export 'deep_link_io.dart' if (dart.library.js_interop) 'deep_link_web.dart';

/// The route [uri]'s fragment names (`/focus?start=1`), or null.
String? routeFromUri(Uri uri) {
  final fragment = uri.fragment;
  return fragment.startsWith('/') && fragment.length > 1 ? fragment : null;
}

/// Whether a new window's `learn <route>` offer is one an open window takes:
/// the lock's `/learn/...`, `/review/...` and `/rework/...` (`web/index.html`
/// offers them).
bool handedOffer(String offer) => const [
  'learn /learn/',
  'learn /review/',
  'learn /rework/',
].any(offer.startsWith);
