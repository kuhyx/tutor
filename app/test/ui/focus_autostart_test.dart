// FocusScreen autoStart: it starts a stopped timer on an active project and
// nothing else (the rest of the screen: focus_screen_test.dart).
import 'package:flutter_test/flutter_test.dart';

import 'focus_support.dart';

void main() {
  testWidgets('autoStart starts a stopped timer on an active project', (
    t,
  ) async {
    await open(t, autoStart: true);
    await t.pump(const Duration(milliseconds: 50));
    expect(find.text('Stop'), findsOneWidget);
    expect(focusEvents().length, 1);
    expect((focusEvents().single! as Map)['event'], 'start');
    await t.tap(find.text('Stop')); // no timer may outlive the test
    await t.pump(const Duration(milliseconds: 50));
  });

  testWidgets('autoStart leaves a running timer alone', (t) async {
    await open(t, autoStart: true, running: true);
    await t.pump(const Duration(milliseconds: 50));
    expect(find.text('Stop'), findsOneWidget);
    expect(focusEvents(), isEmpty);
    await t.tap(find.text('Stop'));
    await t.pump(const Duration(milliseconds: 50));
  });

  testWidgets('autoStart does nothing without an active project', (t) async {
    await open(t, active: false, autoStart: true);
    await t.pump(const Duration(milliseconds: 50));
    expect(focusEvents(), isEmpty);
  });

  testWidgets('without autoStart the timer stays stopped', (t) async {
    await open(t);
    await t.pump(const Duration(milliseconds: 50));
    expect(find.text('Start'), findsOneWidget);
    expect(focusEvents(), isEmpty);
  });
}
