/// Which device the app runs on: the Android app ("phone") or the web build
/// ("desktop"). One seam, the same check the Anki button uses: a phone
/// browser also reports `android`, but it is the web build, so "desktop".
library;

import 'dart:ui' show Size;

import 'package:flutter/foundation.dart';

/// Tests and the screenshot fixture force the answer (null = real check).
bool? debugPhone;

/// The keyboard height (physical-pixel units, before the UI scale) the
/// screenshot fixture pretends is open (null = the real `viewInsets`).
double? debugKeyboardInset;

/// The display size (logical) the screenshot fixture pretends to be on, so a
/// phone shot gets the phone's UI scale, not the Xvfb 4K screen's.
Size? debugDisplay;

/// Phone default for "Display size" when the user never set one (kuhy,
/// 2026-10-15: the phone screen is crowded at 100%).
const double kPhoneZoom = 0.9;

/// Whether this is the Android app.
bool get isPhone =>
    debugPhone ?? (!kIsWeb && defaultTargetPlatform == TargetPlatform.android);

/// `device` of the `message` request: `phone` or `desktop`.
String get deviceName => isPhone ? 'phone' : 'desktop';

/// The "Display size" before the user sets one.
double get defaultZoom => isPhone ? kPhoneZoom : 1;
