// The Plan tile's due button (part e79be0be-1, mockup F7): a module with due
// cards shows a due-count review glyph that runs only that module's due
// cards; a module with nothing due shows none. The replay button stays.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/ui/plan_screen.dart';
import 'package:tutor/ui/review_screen.dart';
import 'package:tutor/widgets/spoken_label.dart';

import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/learn_finders.dart';
import '../support/ui.dart';

const _engine = 'Review The four-stroke engine (2 due)';

/// The car's Plan with engine x2 and fuel x1 due, at [size].
Future<void> _plan(WidgetTester t, Size size) async {
  final db = fixtureDb();
  final s = await fixtureServices(db, FakeStream());
  final month = fixtureNow - 30 * 86400000;
  for (final c in ['eng-strokes', 'eng-crank', 'fuel-spark']) {
    await s.events.record(TaughtEvent(subject: 'car', card: c, at: month));
  }
  await pumpScreen(
    t,
    PlanScreen(services: s, subject: 'car'),
    size: size,
  );
}

Future<void> _check(WidgetTester t) async {
  expect(controlByLabel(_engine), findsOneWidget);
  final button = t.widget<GlyphButton>(glyphsLabelled(_engine));
  expect((button.icon, button.count), (Icons.style, 2));
  expect(controlByLabel('Review Fuel and ignition (1 due)'), findsOneWidget);
  expect(bySpoken('Review Clutch', prefix: true), findsNothing);
  expect(bySpoken('Review Brakes', prefix: true), findsNothing);
  await t.tap(controlByLabel(_engine));
  await t.pumpAndSettle();
  expect(find.byType(ReviewScreen), findsOneWidget);
  expect(spoken('2 left'), findsOneWidget);
  await t.pageBack();
  await t.pumpAndSettle();
  // Back on the Plan, refolded: the button is still there (nothing rated).
  expect(controlByLabel(_engine), findsOneWidget);
}

void main() {
  testWidgets('desktop: the module tile has a due button', (t) async {
    await _plan(t, const Size(1000, 2400));
    await _check(t);
  });

  testWidgets('phone: the module tile has a due button', (t) async {
    await _plan(t, const Size(412, 915));
    await _check(t);
  });
}
