/// "Display size": kuhy's zoom on top of the automatic per-monitor scale
/// (`uiScaleFor`), 50%-200% in 10% steps (kuhy, 2026-10-12).
///
/// Per install, in its own KvStore: the phone and the 4K desktop each keep
/// their own value. Relative, not absolute, so the window keeps its
/// proportions when it moves between the 4K and the QHD monitor. Ctrl + /
/// Ctrl - / Ctrl 0 change it on any hardware keyboard; Chrome's own zoom
/// cannot, because the automatic scale reads the display in CSS pixels and
/// so cancels it out.
library;

import 'dart:async';

import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/util/ui_scale.dart';

/// The current zoom (1 = automatic size), persisted once [load] has run.
class UiZoom extends ValueNotifier<double> {
  /// Starts at [initial] (snapped); nothing is saved until [load].
  new({double initial = 1}) : super(snapZoom(initial));

  /// The KvStore key.
  static const key = 'ui.zoom';

  KvStore? _kv;

  /// Reads the saved zoom from [kv] and saves every later change there.
  Future<void> load(Future<KvStore> kv) async {
    final store = await kv;
    final saved = double.tryParse(await store.get(key) ?? '');
    _kv = store;
    if (saved != null) value = snapZoom(saved);
  }

  /// Sets (snapped) and saves [zoom].
  Future<void> set(double zoom) async {
    value = snapZoom(zoom);
    await _kv?.set(key, '$value');
  }

  /// One 10% step up (+1) or down (-1).
  Future<void> step(int steps) => set(value + steps / kZoomStepsPerUnit);

  /// Back to the automatic size.
  Future<void> reset() => set(1);

  /// Ctrl + / Ctrl - / Ctrl 0 (main row or numpad); true when handled, which
  /// also stops the web build's Chrome from zooming the page itself.
  bool handleKey(KeyEvent event) {
    if (event is KeyUpEvent || !HardwareKeyboard.instance.isControlPressed) {
      return false;
    }
    final k = event.logicalKey;
    final action = switch (k) {
      _ when _plus.contains(k) => () => step(1),
      _ when _minus.contains(k) => () => step(-1),
      _ when _zero.contains(k) => reset,
      _ => null,
    };
    if (action == null) return false;
    unawaited(action());
    return true;
  }

  static final Set<LogicalKeyboardKey> _plus = {
    LogicalKeyboardKey.equal,
    LogicalKeyboardKey.add,
    LogicalKeyboardKey.numpadAdd,
  };
  static final Set<LogicalKeyboardKey> _minus = {
    LogicalKeyboardKey.minus,
    LogicalKeyboardKey.numpadSubtract,
  };
  static final Set<LogicalKeyboardKey> _zero = {
    LogicalKeyboardKey.digit0,
    LogicalKeyboardKey.numpad0,
  };

  /// The app's zoom; 1 outside a [UiZoomHost] (screens tested alone).
  static double of(BuildContext context) =>
      context
          .dependOnInheritedWidgetOfExactType<_UiZoomScope>()
          ?.notifier
          ?.value ??
      1;

  /// The app's [UiZoom] to change; null outside a [UiZoomHost].
  static UiZoom? controllerOf(BuildContext context) =>
      context.getInheritedWidgetOfExactType<_UiZoomScope>()?.notifier;
}

/// Puts [zoom] (or its own, when null) above [child] and listens for the
/// keyboard shortcuts while mounted.
class UiZoomHost extends StatefulWidget {
  /// Creates the host.
  const new({required this.child, this.zoom, super.key});

  /// The zoom to provide; null = an unsaved one owned by the host.
  final UiZoom? zoom;

  /// The app.
  final Widget child;

  @override
  State<UiZoomHost> createState() => _UiZoomHostState();
}

class _UiZoomHostState extends State<UiZoomHost> {
  UiZoom? _own;

  UiZoom get _zoom => widget.zoom ?? (_own ??= UiZoom());

  @override
  void initState() {
    super.initState();
    HardwareKeyboard.instance.addHandler(_onKey);
  }

  @override
  void dispose() {
    HardwareKeyboard.instance.removeHandler(_onKey);
    _own?.dispose();
    super.dispose();
  }

  bool _onKey(KeyEvent event) => _zoom.handleKey(event);

  @override
  Widget build(BuildContext context) =>
      _UiZoomScope(notifier: _zoom, child: widget.child);
}

class _UiZoomScope extends InheritedNotifier<UiZoom> {
  const new({required super.notifier, required super.child});
}
