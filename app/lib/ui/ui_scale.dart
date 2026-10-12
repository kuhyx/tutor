/// Scales the whole app (text, icons, padding, hit targets alike) by
/// `uiScaleFor` the display times kuhy's "Display size" zoom (`UiZoom`), as
/// browser zoom would: below it the app sees a logical window `scale` times
/// smaller, so every breakpoint and width cap works in the same units on
/// every screen.
library;

import 'package:flutter/widgets.dart';
import 'package:tutor/ui/ui_zoom.dart';
import 'package:tutor/util/ui_scale.dart';

/// Applies the display's UI scale and the zoom to [child]
/// (`MaterialApp.builder`, under a `UiZoomHost`).
class UiScale extends StatelessWidget {
  /// Creates the scaler; [display] (logical size) is injectable for tests.
  const new({required this.child, this.display, super.key});

  /// The app.
  final Widget child;

  /// The display's logical size; null reads it from the view.
  final Size? display;

  @override
  Widget build(BuildContext context) {
    final mq = MediaQuery.of(context);
    final screen = display ?? _displayOf(context);
    final s = uiScaleFor(screen) * UiZoom.of(context);
    // Always the same tree, even at 1: switching shape when the zoom crosses
    // 100% would remount [child] (the Navigator) and drop every open screen.
    final size = mq.size / s;
    return FittedBox(
      fit: BoxFit.fill,
      alignment: Alignment.topLeft,
      child: SizedBox.fromSize(
        size: size,
        child: MediaQuery(
          data: mq.copyWith(
            size: size,
            devicePixelRatio: mq.devicePixelRatio * s,
            padding: mq.padding / s,
            viewPadding: mq.viewPadding / s,
            viewInsets: mq.viewInsets / s,
          ),
          child: child,
        ),
      ),
    );
  }

  static Size _displayOf(BuildContext context) {
    final d = View.of(context).display;
    return d.size / d.devicePixelRatio;
  }
}
