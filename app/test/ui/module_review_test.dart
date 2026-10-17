// "Module Anki": a done-but-not-reviewed module offers "Review this
// module" (Home, Plan); the run holds every taught card of the module and
// re-queues Again/Hard until Good/Easy.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/plan_screen.dart';
import 'package:tutor/ui/review_screen.dart';

import '../support/fake_stream.dart';
import '../support/ui.dart';

/// Teaches [cards] of the fixture's `car` just now (nothing is due).
Future<TutorServices> _taught(List<String> cards) async {
  final s = await fixtureServices(fixtureDb(), FakeStream());
  for (final c in cards) {
    await s.events.record(TaughtEvent(subject: 'car', card: c, at: fixtureNow));
  }
  return s;
}

Future<void> _rate(WidgetTester t, String grade) async {
  await t.tap(find.text('Show answer (Space)'));
  await t.pumpAndSettle();
  await t.tap(find.text(grade));
  await t.pumpAndSettle();
}

void main() {
  testWidgets('Home: Review <module> runs its cards; Again comes back', (
    t,
  ) async {
    // fuel has one card in the catalog; engine is "mastered" on the PC.
    final s = await _taught(['fuel-spark', 'eng-strokes']);
    await pumpScreen(
      t,
      HomeScreen(services: s, onSignedOut: () {}),
      size: const Size(412, 1400),
    );
    expect(find.text('Review Fuel and ignition'), findsOneWidget);
    expect(find.text('Review The four-stroke engine'), findsNothing);
    await t.tap(find.text('Review Fuel and ignition'));
    await t.pumpAndSettle();
    expect(find.textContaining('Fuel and ignition'), findsWidgets);
    expect(find.textContaining('1 left'), findsOneWidget);
    await _rate(t, '1 Again');
    expect(find.text('What ignites the mixture?'), findsOneWidget);
    expect(find.textContaining('1 left'), findsOneWidget);
    await _rate(t, '2 Hard');
    expect(find.text('What ignites the mixture?'), findsOneWidget);
    await _rate(t, '3 Good');
    expect(find.text('All done'), findsOneWidget);
    expect(find.textContaining('Reviewed 1 card'), findsOneWidget);
    final grades = (await s.events.all())
        .map((e) => e.event)
        .whereType<ReviewEvent>()
        .map((e) => e.grade);
    expect(grades, [Grade.again, Grade.hard, Grade.good]);
    // Back on Home the module is reviewed: no action any more.
    await t.pageBack();
    await t.pumpAndSettle();
    expect(find.text('Review Fuel and ignition'), findsNothing);
  });

  testWidgets('Plan: Review this module on a done module only', (t) async {
    final s = await _taught(['fuel-spark']);
    await pumpScreen(t, PlanScreen(services: s, subject: 'car'));
    expect(find.text('Review this module'), findsOneWidget);
    await t.tap(find.text('Review this module'));
    await t.pumpAndSettle();
    expect(find.text('What ignites the mixture?'), findsOneWidget);
    expect(find.textContaining('1 left'), findsOneWidget);
  });

  testWidgets('Plan: nothing taught, nothing to review', (t) async {
    final s = await _taught([]);
    await pumpScreen(t, PlanScreen(services: s, subject: 'car'));
    expect(find.text('Review this module'), findsNothing);
    await pumpScreen(
      t,
      ReviewScreen(
        services: s,
        module: const ModuleRef(subject: 'car', module: 'fuel', title: 'F'),
      ),
    );
    expect(find.text('Review: F'), findsOneWidget);
    expect(find.text('Nothing to review'), findsOneWidget);
  });
}
