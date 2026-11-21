/// The Session screen's input chrome: the phone keyboard's effect on the
/// status bar and sidebar, and wheel forwarding to the chat.
library;

import 'dart:async';

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Tracks the phone keyboard: while it is up the Android status bar (clock,
/// battery) is hidden and the nav bar stays (kuhy, 2026-11-10).
class SessionKeyboard {
  /// Creates the tracker for the screen's [scaffold].
  new(this.scaffold);

  /// The screen's scaffold, whose sidebar a rising keyboard closes.
  final GlobalKey<ScaffoldState> scaffold;

  bool _keyboard = false; // phone keyboard up at the last build

  static Future<void> _statusBar({required bool show}) => show
      ? SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge)
      : SystemChrome.setEnabledSystemUIMode(
          SystemUiMode.manual,
          overlays: const [SystemUiOverlay.bottom],
        );

  /// The keyboard rose or fell: the status bar follows, and a rising
  /// keyboard closes the sidebar (it cannot be opened while it is up).
  void changed({required bool keyboard}) {
    if (keyboard == _keyboard) return;
    _keyboard = keyboard;
    unawaited(_statusBar(show: !keyboard));
    if (keyboard) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final s = scaffold.currentState;
        if (s != null && s.isEndDrawerOpen) s.closeEndDrawer();
      });
    }
  }

  /// The screen is going: a hidden status bar comes back.
  void dispose() {
    if (_keyboard) unawaited(_statusBar(show: true));
  }
}

/// Forwards a wheel over the margins/buttons to the chat's [scroll]
/// (`wheel.js`): anything that scrolls itself (the chat, a text box) claims
/// it first.
void forwardWheel(ScrollController scroll, PointerSignalEvent e) {
  if (e is! PointerScrollEvent || !scroll.hasClients) return;
  GestureBinding.instance.pointerSignalResolver.register(e, (event) {
    final p = scroll.position;
    final d = (event as PointerScrollEvent).scrollDelta.dy;
    // The chat list is reversed: wheel down = toward offset 0.
    scroll.jumpTo((p.pixels - d).clamp(0, p.maxScrollExtent));
  });
}
