import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/sql/lesson_screen.dart';

import '../../sql/sql_fixtures.dart';
import '../../support/fake_rtdb.dart';
import '../../support/fake_stream.dart';
import '../../support/services.dart';
import '../../support/ui.dart';

void main() {
  Future<void> open(WidgetTester t, {required double keyboard}) async {
    final db = FakeRtdb();
    final stream = FakeStream();
    await pumpScreen(
      t,
      SqlLessonScreen(services: services(db, stream), topic: 'basics'),
      settle: false,
    );
    t.view
      ..physicalSize = const Size(1080, 2400)
      ..devicePixelRatio = 2.625
      ..padding = const FakeViewPadding(top: 132, bottom: 63)
      ..viewInsets = FakeViewPadding(bottom: keyboard);
    await t.pump(const Duration(milliseconds: 50));
    await answer(t, db, stream, data: lessonTurnData);
  }

  testWidgets('typing keeps a compact table strip in view (30% cap)', (
    t,
  ) async {
    await open(t, keyboard: 800);
    await t.tap(find.byKey(const ValueKey('answer')));
    await t.pump(const Duration(milliseconds: 100));
    const dpr = 2.625;
    const keyboardTop = (2400 - 800) / dpr;
    const visible = (2400 - 800 - 132) / dpr;
    final strip = find.byKey(const ValueKey('table-strip'));
    final box = t.getRect(find.byKey(const ValueKey('answer')));
    expect(find.byKey(const ValueKey('tables-header')), findsNothing);
    expect(strip, findsOneWidget);
    expect(strip.hitTestable(), findsOneWidget);
    expect(
      find.descendant(of: strip, matching: find.text('Ann')),
      findsOneWidget,
    );
    expect(t.getSize(strip).height, lessThanOrEqualTo(visible * 0.3 + 0.5));
    expect(t.getRect(strip).top, greaterThanOrEqualTo(132 / dpr));
    expect(box.bottom, lessThanOrEqualTo(keyboardTop));
    expect(box.top, greaterThan(t.getRect(strip).bottom));
    final x = find.byKey(const ValueKey('table-strip-x'));
    expect(t.widget<SingleChildScrollView>(x).scrollDirection, Axis.horizontal);
  });

  testWidgets('the full tables come back when the box loses focus', (t) async {
    await open(t, keyboard: 800);
    await t.tap(find.byKey(const ValueKey('answer')));
    await t.pump(const Duration(milliseconds: 100));
    FocusManager.instance.primaryFocus?.unfocus();
    await t.pump(const Duration(milliseconds: 100));
    expect(find.byKey(const ValueKey('table-strip')), findsNothing);
    expect(find.byKey(const ValueKey('tables-header')), findsOneWidget);
  });
}
