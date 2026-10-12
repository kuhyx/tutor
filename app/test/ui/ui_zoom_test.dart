import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/ui/display_size_dialog.dart';
import 'package:tutor/ui/ui_scale.dart';
import 'package:tutor/ui/ui_zoom.dart';
import 'package:tutor/util/ui_scale.dart';

void main() {
  test('snapZoom: 50%-200% in 10% steps, no float drift', () {
    expect(snapZoom(1), 1);
    expect(snapZoom(0.1), kMinZoom);
    expect(snapZoom(9), kMaxZoom);
    expect(snapZoom(1.26), 1.3);
    expect(snapZoom(0.1 + 0.2 + 0.7 + 0.1), 1.1);
  });

  test('load reads the saved zoom, later changes are saved', () async {
    final kv = MemoryKv()..data[UiZoom.key] = '1.5';
    final zoom = UiZoom();
    await zoom.set(1.2); // before load: nowhere to save yet
    expect(kv.data[UiZoom.key], '1.5');
    await zoom.load(Future.value(kv));
    expect(zoom.value, 1.5);
    await zoom.step(1);
    expect(kv.data[UiZoom.key], '1.6');
    await zoom.step(-3);
    expect(zoom.value, 1.3);
    await zoom.reset();
    expect(kv.data[UiZoom.key], '1.0');
    // A missing or garbled value keeps the current zoom.
    kv.data[UiZoom.key] = 'huge';
    await zoom.load(Future.value(kv));
    expect(zoom.value, 1);
    expect(UiZoom(initial: 7).value, kMaxZoom);
  });

  testWidgets('Ctrl + / Ctrl - / Ctrl 0 change the zoom; others pass', (
    t,
  ) async {
    final zoom = UiZoom();
    await t.pumpWidget(UiZoomHost(zoom: zoom, child: const SizedBox()));
    Future<bool> ctrl(LogicalKeyboardKey key) async {
      await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      final handled = await t.sendKeyEvent(key);
      await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      return handled;
    }

    expect(await ctrl(LogicalKeyboardKey.equal), isTrue);
    expect(await ctrl(LogicalKeyboardKey.numpadAdd), isTrue);
    expect(zoom.value, 1.2);
    expect(await ctrl(LogicalKeyboardKey.minus), isTrue);
    expect(zoom.value, 1.1);
    expect(await ctrl(LogicalKeyboardKey.numpad0), isTrue);
    expect(zoom.value, 1);
    expect(await ctrl(LogicalKeyboardKey.keyA), isFalse);
    // Without Ctrl, "=" is just typing.
    expect(await t.sendKeyEvent(LogicalKeyboardKey.equal), isFalse);
    expect(zoom.value, 1);
    // Unmounted: the handler is gone.
    await t.pumpWidget(const SizedBox());
    await ctrl(LogicalKeyboardKey.equal);
    expect(zoom.value, 1);
  });

  testWidgets('UiScale multiplies the display scale by the zoom', (t) async {
    t.view.physicalSize = const Size(2000, 2000);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.reset);
    final zoom = UiZoom();
    Size? seen;
    var builds = 0;
    await t.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(size: Size(2000, 2000)),
        child: UiZoomHost(
          zoom: zoom,
          child: UiScale(
            display: const Size(1920, 1080),
            child: _Counter(onInit: () => builds++, onBuild: (s) => seen = s),
          ),
        ),
      ),
    );
    expect(seen, const Size(2000, 2000));
    await zoom.set(2);
    await t.pump();
    expect(seen, const Size(1000, 1000));
    await zoom.set(0.5);
    await t.pump();
    expect(seen, const Size(4000, 4000));
    // Crossing 100% keeps the subtree (the Navigator) mounted.
    expect(builds, 1);
  });

  testWidgets('without a host: zoom 1, no controller, own zoom', (t) async {
    double? of;
    UiZoom? controller;
    await t.pumpWidget(
      Builder(
        builder: (context) {
          of = UiZoom.of(context);
          controller = UiZoom.controllerOf(context);
          return const SizedBox();
        },
      ),
    );
    expect((of, controller), (1.0, null));
    await t.pumpWidget(
      UiZoomHost(
        child: Builder(
          builder: (context) {
            controller = UiZoom.controllerOf(context);
            return const SizedBox();
          },
        ),
      ),
    );
    expect(controller?.value, 1);
    await t.pumpWidget(const SizedBox()); // disposes the host's own zoom
  });

  testWidgets('dialog: drag applies on release, Reset, Done', (t) async {
    final kv = MemoryKv();
    final zoom = UiZoom();
    await zoom.load(Future.value(kv));
    await t.pumpWidget(
      MaterialApp(
        builder: (context, child) => UiZoomHost(zoom: zoom, child: child!),
        home: Builder(
          builder: (context) => TextButton(
            onPressed: () => showDisplaySize(context),
            child: const Text('open'),
          ),
        ),
      ),
    );
    await t.tap(find.text('open'));
    await t.pumpAndSettle();
    expect(find.text('100%'), findsOneWidget);
    final slider = find.byType(Slider);
    // From 100% (1/3 along) to the right end: 200%.
    final gesture = await t.startGesture(t.getCenter(slider));
    await gesture.moveBy(Offset(t.getSize(slider).width, 0));
    await t.pump();
    expect(zoom.value, 1, reason: 'nothing applied mid-drag');
    expect(find.text('200%'), findsOneWidget);
    await gesture.up();
    await t.pumpAndSettle();
    expect(zoom.value, 2);
    expect(kv.data[UiZoom.key], '2.0');
    await t.tap(find.text('Reset to auto'));
    await t.pumpAndSettle();
    expect(zoom.value, 1);
    expect(find.text('100%'), findsOneWidget);
    await t.tap(find.text('Done'));
    await t.pumpAndSettle();
    expect(find.byType(Slider), findsNothing);
  });
}

class _Counter extends StatefulWidget {
  const new({required this.onInit, required this.onBuild});

  final VoidCallback onInit;
  final void Function(Size) onBuild;

  @override
  State<_Counter> createState() => _CounterState();
}

class _CounterState extends State<_Counter> {
  @override
  void initState() {
    super.initState();
    widget.onInit();
  }

  @override
  Widget build(BuildContext context) {
    widget.onBuild(MediaQuery.sizeOf(context));
    return const SizedBox.expand();
  }
}
