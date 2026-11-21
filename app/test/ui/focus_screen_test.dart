// FocusScreen: project, ring, gates, Start/Stop and Edit (autoStart:
// focus_autostart_test.dart; harness: focus_support.dart).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/focus_form.dart';

import '../support/no_words.dart';
import 'focus_support.dart';

void main() {
  testWidgets('shows the project, ring, off and kept gates', (t) async {
    await open(t);
    expect(find.text('HackerRank prep'), findsOneWidget);
    expect(find.text('4 days left'), findsOneWidget);
    expect(find.text('42'), findsOneWidget);
    expect(find.text('120'), findsOneWidget);
    expect(find.text('LeetCode'), findsOneWidget);
    expect(find.text('Workout'), findsOneWidget);
    expect(find.text('Start'), findsOneWidget);
  });

  testWidgets('overtime shows the real minutes and what is banked', (t) async {
    await open(t, minutes: 121);
    expect(find.text('121'), findsOneWidget);
    expect(find.text('120'), findsOneWidget);
    expect(find.text('(+1 banked)'), findsOneWidget);
  });

  testWidgets('the bank shown is capped at the 60 the server banks', (t) async {
    await open(t, minutes: 300);
    expect(find.text('(+60 banked)'), findsOneWidget);
  });

  testWidgets('unbacked minutes show under the ring', (t) async {
    await open(t, unbacked: 12);
    final mark = find.byKey(const ValueKey('unbacked'));
    expect(mark, findsOneWidget);
    expect(
      find.descendant(
        of: mark,
        matching: find.byIcon(Icons.timer_off_outlined),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(of: mark, matching: find.text('12')),
      findsOneWidget,
    );
    expect(
      find.bySemanticsLabel('12 min unbacked (not counted)'),
      findsOneWidget,
    );
    expect(find.textContaining('unbacked'), findsNothing);
    expectNoWords(t, 'focus with unbacked minutes');
  });

  testWidgets('no unbacked minutes, no unbacked line', (t) async {
    await open(t, unbacked: 0);
    expect(find.byKey(const ValueKey('unbacked')), findsNothing);
  });

  testWidgets('an older server without the field shows no line', (t) async {
    await open(t);
    expect(find.byKey(const ValueKey('unbacked')), findsNothing);
  });

  testWidgets('no project, no unbacked line', (t) async {
    await open(t, active: false, unbacked: 5);
    expect(find.byKey(const ValueKey('unbacked')), findsNothing);
  });

  testWidgets('the ring moves on server figures, not the running clock', (
    t,
  ) async {
    // 4 min 59 s into a run: the client clock reaches 5 min a second after
    // the status loads; the ring must stay at the server's 42.
    await open(t, running: true, lastAgoMs: 299000);
    await t.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 1500)),
    );
    await t.pump(const Duration(seconds: 2));
    expect(find.text('42'), findsOneWidget);
    expect(find.text('43'), findsNothing);
    await t.tap(find.text('Stop'));
    await t.pump(const Duration(milliseconds: 50));
  });

  testWidgets('Start refreshes the status', (t) async {
    await open(t);
    final before = statusRequests();
    await t.tap(find.text('Start'));
    await t.pump(const Duration(milliseconds: 50));
    expect(statusRequests(), before + 1);
    await t.tap(find.text('Stop'));
    await t.pump(const Duration(milliseconds: 50));
  });

  testWidgets('no overtime, no bank line', (t) async {
    await open(t);
    expect(find.textContaining('banked'), findsNothing);
  });

  testWidgets('Start queues a start tap with its time; Stop ends it', (
    t,
  ) async {
    await open(t);
    await t.tap(find.text('Start'));
    await t.pump(const Duration(milliseconds: 50));
    expect(find.text('Stop'), findsOneWidget);
    // The status is asked again after the tap, so it is not the last request.
    final body = focusEvents().single! as Map<String, dynamic>;
    expect(body['event'], 'start');
    expect(body['platform'], 'phone');
    expect(body['ts'], isA<int>());
    await t.tap(find.text('Stop'));
    await t.pump(const Duration(milliseconds: 50));
    expect(find.text('Start'), findsOneWidget);
  });

  testWidgets('Edit opens the form on the active project', (t) async {
    await open(t);
    await t.tap(find.text('Edit'));
    await t.pumpAndSettle();
    expect(find.byType(FocusFormScreen), findsOneWidget);
    expect(find.text('hackerrank.com'), findsOneWidget);
    expect(find.text('Save'), findsOneWidget);
  });

  testWidgets('no project: only New project', (t) async {
    await open(t, active: false);
    expect(find.text('No focus project'), findsOneWidget);
    expect(find.text('New project'), findsOneWidget);
    expect(find.text('Start'), findsNothing);
  });

  testWidgets('fits a Pixel 6a screen with no scrolling', (t) async {
    t.view
      ..physicalSize = const Size(1080, 2400)
      ..devicePixelRatio = 2.625
      ..padding = const FakeViewPadding(top: 132, bottom: 63);
    addTearDown(t.view.reset);
    await open(t);
    expect(find.byType(Scrollable), findsNothing);
    final start = t.getRect(find.text('Start'));
    expect(start.bottom, lessThan(2400 / 2.625 - 63 / 2.625));
  });
}
