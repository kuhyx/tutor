import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/home_screen.dart';

import '../support/fake_stream.dart';
import '../support/ui.dart';

void main() {
  testWidgets('Home menu opens the mock test start screen', (t) async {
    final s = await fixtureServices(fixtureDb(), FakeStream());
    await pumpScreen(t, HomeScreen(services: s, onSignedOut: () {}));
    await t.tap(find.byTooltip('More'));
    await t.pumpAndSettle();
    await t.tap(find.byIcon(Icons.quiz_outlined));
    await t.pumpAndSettle();
    expect(find.byKey(const ValueKey('start')), findsOneWidget);
  });
}
