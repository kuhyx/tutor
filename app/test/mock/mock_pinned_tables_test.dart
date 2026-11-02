import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'mock_support.dart';

void main() {
  testWidgets(
    'a typed SQL task keeps its tables in a strip with the keyboard',
    (t) async {
      await Rig().pumpTest(t);
      t.view
        ..physicalSize = const Size(1080, 2400)
        ..devicePixelRatio = 2.625
        ..padding = const FakeViewPadding(top: 132, bottom: 63);
      await t.tap(find.byKey(const ValueKey('nav-3')));
      await t.pump();
      final strip = find.byKey(const ValueKey('table-strip'));
      expect(strip, findsNothing);
      await t.tap(find.byType(EditableText));
      t.view.viewInsets = const FakeViewPadding(bottom: 800);
      await t.pump(const Duration(milliseconds: 100));
      const visible = (2400 - 800 - 132) / 2.625;
      expect(strip, findsOneWidget);
      expect(strip.hitTestable(), findsOneWidget);
      expect(
        find.descendant(of: strip, matching: find.text('Ann')),
        findsOneWidget,
      );
      expect(find.text('c'), findsOneWidget); // only the strip's copy
      expect(t.getSize(strip).height, lessThanOrEqualTo(visible * 0.3 + 0.5));
      expect(find.byType(EditableText), findsOneWidget);
      expect(
        t.widget<EditableText>(find.byType(EditableText)).focusNode.hasFocus,
        isTrue,
      );
      t.view.viewInsets = FakeViewPadding.zero;
      await t.pump(const Duration(milliseconds: 100));
      expect(strip, findsNothing);
      expect(find.text('Ann'), findsWidgets);
    },
  );
}
