/// The desktop (web build) check-in notification: the browser's
/// `Notification`, armed by the focus timer like the Android one (C2).
///
/// A conditional export: the web half needs `dart:js_interop`, which the
/// Android build cannot compile; there the factory returns the no-op.
library;

export 'web_checkin_io.dart'
    if (dart.library.js_interop) 'web_checkin_web.dart';
