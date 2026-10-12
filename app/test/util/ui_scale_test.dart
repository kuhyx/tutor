import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/ui_scale.dart';
import 'package:tutor/util/ui_scale.dart';

void main() {
  test('scale by display: 4K x2, QHD x1.33, full HD and phones x1', () {
    // kuhy, 2026-10-12: on the 4K monitor (DPR 1) text was unreadable.
    expect(uiScaleFor(const Size(3840, 2160)), 2);
    expect(uiScaleFor(const Size(2160, 3840)), 2); // portrait
    expect(uiScaleFor(const Size(2560, 1440)), 1.33);
    expect(uiScaleFor(const Size(1920, 1080)), 1);
    expect(uiScaleFor(const Size(1376, 780)), 1);
    expect(uiScaleFor(const Size(412, 915)), 1);
    expect(uiScaleFor(const Size(7680, 4320)), kMaxUiScale);
    expect(uiScaleFor(Size.zero), 1);
  });

  testWidgets('the app below sees a window scale times smaller', (t) async {
    t.view.physicalSize = const Size(2000, 2100);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.reset);
    Size? seen;
    double? dpr;
    Widget app(Size display) => MediaQuery(
      data: const MediaQueryData(size: Size(2000, 2100)),
      child: UiScale(
        display: display,
        child: Builder(
          builder: (context) {
            seen = MediaQuery.sizeOf(context);
            dpr = MediaQuery.devicePixelRatioOf(context);
            return const SizedBox.expand();
          },
        ),
      ),
    );
    await t.pumpWidget(app(const Size(3840, 2160)));
    expect(seen, const Size(1000, 1050));
    expect(dpr, 2);
    await t.pumpWidget(app(const Size(1920, 1080)));
    expect(seen, const Size(2000, 2100));
    // Without an injected display it reads the view's.
    final d = t.view.display;
    final s = uiScaleFor(d.size / d.devicePixelRatio);
    await t.pumpWidget(
      UiScale(
        child: Builder(
          builder: (context) {
            seen = MediaQuery.sizeOf(context);
            return const SizedBox.expand();
          },
        ),
      ),
    );
    expect(seen, const Size(2000, 2100) / s);
  });
}
