import 'package:flutter/material.dart';

/// Dp above the keyboard and below the status bar.
double visibleHeight(BuildContext context) {
  final v = View.of(context);
  final px = v.physicalSize.height - v.viewInsets.bottom - v.padding.top;
  return px / v.devicePixelRatio;
}

/// Whether the on-screen keyboard is up.
bool keyboardUp(BuildContext context) => View.of(context).viewInsets.bottom > 0;

/// Rebuilds [builder] whenever the window metrics (the keyboard) change.
class MetricsBuilder extends StatefulWidget {
  /// Creates the builder.
  const new({required this.builder, super.key});

  /// Builds the child.
  final WidgetBuilder builder;

  @override
  State<MetricsBuilder> createState() => _MetricsBuilderState();
}

class _MetricsBuilderState extends State<MetricsBuilder>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeMetrics() => setState(() {});

  @override
  Widget build(BuildContext context) => widget.builder(context);
}

/// [child] at most [share] of the visible height tall.
class CappedHeight extends StatelessWidget {
  /// Creates the cap.
  const new({required this.share, required this.child, super.key});

  /// Part of [visibleHeight].
  final double share;

  /// What to cap.
  final Widget child;

  @override
  Widget build(BuildContext context) => MetricsBuilder(
    builder: (c) => ConstrainedBox(
      constraints: BoxConstraints(maxHeight: visibleHeight(c) * share),
      child: child,
    ),
  );
}
