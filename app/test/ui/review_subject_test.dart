// Subject-scoped review: a subject's Review shows only its own due cards;
// Home's global Review stays global but says how the due cards split.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/widgets/spoken_label.dart';

import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/learn_finders.dart';
import '../support/ui.dart';

void main() {
  testWidgets('a subject tile reviews only that subject', (t) async {
    final db = fixtureDb();
    final card = getAt(db.root, 'tutor/v1/subjects/car/cards/eng-crank')!;
    db.root = setAt(db.root, 'tutor/v1/subjects/garden/cards', {
      'g-sun': {
        ...card as Map<String, dynamic>,
        'module': 'light',
        'front': 'How many hours of sun do tomatoes need?',
      },
    });
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    final month = DateTime.fromMillisecondsSinceEpoch(fixtureNow)
        .subtract(const Duration(days: 30))
        .millisecondsSinceEpoch;
    for (final (subject, c) in [
      ('car', 'eng-strokes'),
      ('car', 'eng-crank'),
      ('garden', 'g-sun'),
    ]) {
      await s.events.record(TaughtEvent(subject: subject, card: c, at: month));
    }
    await pumpScreen(
      t,
      HomeScreen(services: s, onSignedOut: () {}),
      size: const Size(1366, 1400),
    );
    // Global: its count as the badge (the per-subject tooltip is gone: a
    // tooltip paints words).
    expect(controlByLabel('Review (3 due)'), findsOneWidget);
    expect(t.widget<GlyphButton>(glyphsLabelled('Review (3 due)')).count, 3);
    // Each tile: its own count and button.
    expect(controlByLabel('Review (2 due)'), findsOneWidget);
    expect(controlByLabel('Review (1 due)'), findsOneWidget);

    await t.tap(controlByLabel('Review (1 due)'));
    await t.pumpAndSettle();
    expect(spoken('Review: Vegetable gardening'), findsOneWidget);
    expect(spoken('1 left'), findsOneWidget);
    expect(
      find.text('How many hours of sun do tomatoes need?'),
      findsOneWidget,
    );
    expect(find.textContaining('How a car works'), findsNothing);
  });
}
