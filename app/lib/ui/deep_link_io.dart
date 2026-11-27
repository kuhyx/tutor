/// The non-web half of `deep_link.dart`: no address bar; on Android the
/// `kuhytutor://` links leetcode-guard's phone app opens (`DeepLinkChannel.kt`).
library;

import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:tutor/ui/deep_link.dart' show routeFromAppLink;

const _links = MethodChannel('com.kuhy.tutor/deeplink');
const _newLinks = EventChannel('com.kuhy.tutor/deeplink/new');

/// Whether MainActivity's link channels exist (Android only; tests set it).
@visibleForTesting
bool appLinksAvailable = Platform.isAndroid;

String? _route(Object? link) {
  final uri = link is String ? Uri.tryParse(link) : null;
  return uri == null ? null : routeFromAppLink(uri);
}

/// Nothing to forget off the web.
void forgetDeepLink() {}

/// One window per app off the web already.
void joinWindows() {}

/// The route the app was launched with: the launch intent's link, which
/// MainActivity hands out once; null without one or on any channel failure.
Future<String?> initialRoute() async {
  if (!appLinksAvailable) return null;
  try {
    return _route(await _links.invokeMethod<Object?>('initialLink'));
  } on MissingPluginException catch (e) {
    debugPrint('deep link: $e');
  } on PlatformException catch (e) {
    debugPrint('deep link: $e');
  }
  return null;
}

/// The route of each link sent to the running app (Android's onNewIntent).
Stream<String> get handedRoutes => appLinksAvailable
    ? _newLinks.receiveBroadcastStream().expand((link) => [?_route(link)])
    : const Stream.empty();
