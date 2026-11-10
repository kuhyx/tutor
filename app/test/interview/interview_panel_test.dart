import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '_data.dart';
import '_panel_harness.dart';

void main() {
  final h = PanelHarness();

  testWidgets('an old-protocol status shows no interview row', (t) async {
    await h.open(t, {...oldProject, 'minutes': 3});
    for (final n in ['rules', 'trip', 'phone', 'clock', 'mock', 'slot']) {
      expect(h.key(n), findsNothing, reason: n);
    }
  });

  testWidgets('the row has the six icons and not one word', (t) async {
    await h.open(t, interviewProject());
    for (final n in ['rules', 'trip', 'phone', 'clock', 'mock', 'slot']) {
      expect(h.key(n), findsOneWidget, reason: n);
    }
    expect(
      find.descendant(
        of: find.byKey(const ValueKey('interview-row')),
        matching: find.byType(Text),
      ),
      findsNothing,
    );
  });

  testWidgets('each icon is labelled for assistive tech', (t) async {
    final sem = t.ensureSemantics();
    await h.open(t, interviewProject());
    for (final n in ['rules', 'trip', 'phone', 'clock', 'mock', 'slot']) {
      expect(find.bySemanticsLabel('interview-ms-$n'), findsOneWidget);
    }
    sem.dispose();
  });

  testWidgets('grey pending, green done/late_done, red missed/unknown', (
    t,
  ) async {
    await h.open(
      t,
      interviewProject(
        milestones: [
          ms('rules', '2026-11-10T23:59:00', 'late_done'),
          ms('trip_ask:2026-11-14', '2026-11-12T23:59:00', 'done'),
          ms('phone:2026-11-14', '2026-11-13T12:00:00', 'missed'),
          ms('mock', '2026-11-18T23:59:00', 'pending'),
          ms('slot', '2026-11-19T12:00:00', 'unknown'),
        ],
      ),
    );
    expect(h.colorOf(t, 'rules'), AppPalette.success);
    expect(h.colorOf(t, 'trip'), AppPalette.success);
    expect(h.colorOf(t, 'phone'), AppPalette.danger);
    expect(h.colorOf(t, 'slot'), AppPalette.danger);
    final grey = h.colorOf(t, 'mock');
    expect(grey, isNot(AppPalette.success));
    expect(grey, isNot(AppPalette.danger));
  });

  testWidgets('the clock is grey below the target', (t) async {
    await h.open(t, interviewProject(minutes: 12));
    expect(h.colorOf(t, 'clock'), isNot(AppPalette.success));
  });

  testWidgets('the clock is green once the minutes reach the target', (
    t,
  ) async {
    await h.open(t, interviewProject(minutes: 30));
    expect(h.colorOf(t, 'clock'), AppPalette.success);
  });

  testWidgets('a color is never the only cue: done and red wear a badge', (
    t,
  ) async {
    await h.open(
      t,
      interviewProject(
        milestones: [
          ms('rules', '2026-11-10T23:59:00', 'done'),
          ms('mock', '2026-11-18T23:59:00', 'missed'),
          ms('slot', '2026-11-19T12:00:00', 'pending'),
        ],
      ),
    );
    Finder icons(String n) =>
        find.descendant(of: h.key(n), matching: find.byType(Icon));
    expect(icons('rules'), findsNWidgets(2));
    expect(icons('mock'), findsNWidgets(2));
    expect(icons('slot'), findsOneWidget);
  });
}
