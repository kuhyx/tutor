// The phone keyboard and the Android status bar (todo 340c295b-10): the bar
// hides with the keyboard and comes back on close and on leaving the screen;
// the desktop ignores keyboard insets.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/util/device.dart';

import '../support/composer.dart';
import '../support/fit.dart';

Finder get _field => find.byType(TextField).hitTestable();

Future<void> _keyboardUp(WidgetTester t) async {
  pixelView(t, keyboard: 300);
  await t.pumpAndSettle();
}

Future<void> _keyboardDown(WidgetTester t) async {
  pixelView(t);
  await t.pumpAndSettle();
}

/// SystemChrome system-UI calls, in order (fake platform channel).
List<MethodCall> _recordChrome(WidgetTester t) {
  final calls = <MethodCall>[];
  t.binding.defaultBinaryMessenger.setMockMethodCallHandler(
    SystemChannels.platform,
    (call) async {
      if (call.method.startsWith('SystemChrome.setEnabledSystemUI')) {
        calls.add(call);
      }
      return null;
    },
  );
  addTearDown(
    () => t.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      null,
    ),
  );
  return calls;
}

void main() {
  tearDown(() => debugPhone = null);

  testWidgets('status bar hides with the keyboard, back on close and leave', (
    t,
  ) async {
    final calls = _recordChrome(t);
    await openComposer(t, phone: true);
    pixelView(t);
    await t.pumpAndSettle();
    expect(calls, isEmpty);
    await openField(t);
    await _keyboardUp(t);
    expect(calls, hasLength(1));
    expect(calls.last.method, 'SystemChrome.setEnabledSystemUIOverlays');
    expect(calls.last.arguments, ['SystemUiOverlay.bottom']);
    await _keyboardDown(t);
    expect(calls, hasLength(2));
    expect(calls.last.method, 'SystemChrome.setEnabledSystemUIMode');
    expect(calls.last.arguments, 'SystemUiMode.edgeToEdge');
    // Up again, then leave the screen: restored.
    await t.tap(_field.first);
    await _keyboardUp(t);
    expect(calls, hasLength(3));
    await t.pumpWidget(const SizedBox());
    expect(calls, hasLength(4));
    expect(calls.last.arguments, 'SystemUiMode.edgeToEdge');
  });

  testWidgets('desktop: keyboard insets change nothing', (t) async {
    final calls = _recordChrome(t);
    await openComposer(t, phone: false);
    t.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(t.view.resetViewInsets);
    await t.pumpAndSettle();
    expect(find.byType(AppBar), findsOneWidget);
    expect(find.byIcon(Icons.edit_outlined), findsNWidgets(3));
    expect(calls, isEmpty);
  });
}
