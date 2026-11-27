// The due badge opens a module sheet (part e79be0be-1, mockup F6): one row
// per module with due cards, then the whole subject. A module row runs that
// module's due cards only, the subject row all of them.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/review_screen.dart';
import 'package:tutor/ui/subject_tile.dart';

import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/learn_finders.dart';
import '../support/ui.dart';

/// Home over the fixture with engine x2 and fuel x1 due (taught a month
/// ago), at [size].
Future<TutorServices> _home(WidgetTester t, Size size) async {
  final db = fixtureDb();
  final s = await fixtureServices(db, FakeStream());
  final month = fixtureNow - 30 * 86400000;
  for (final c in ['eng-strokes', 'eng-crank', 'fuel-spark']) {
    await s.events.record(TaughtEvent(subject: 'car', card: c, at: month));
  }
  await pumpScreen(
    t,
    HomeScreen(services: s, onSignedOut: () {}),
    size: size,
  );
  return s;
}

const _engine = 'Review The four-stroke engine (2 due)';
const _fuel = 'Review Fuel and ignition (1 due)';
const _all = 'Review all (3 due)';

Future<void> _tap(WidgetTester t, Finder f) async {
  await t.tap(f);
  await t.pumpAndSettle();
}

Future<void> _back(WidgetTester t) async {
  await t.pageBack();
  await t.pumpAndSettle();
}

void main() {
  testWidgets('phone: the red badge opens the module sheet', (t) async {
    await _home(t, const Size(412, 915));
    expect(find.byType(BottomSheet), findsNothing);
    await _tap(t, controlByLabel('Review by module (3 due)'));
    expect(find.byType(BottomSheet), findsOneWidget);
    expect(controlByLabel(_engine), findsOneWidget);
    expect(controlByLabel(_fuel), findsOneWidget);
    expect(controlByLabel(_all), findsOneWidget);
    // Nothing due: no row.
    expect(bySpoken('Review Clutch', prefix: true), findsNothing);
    expect(find.byIcon(Icons.all_inclusive), findsOneWidget);
    // Only counts are painted beside the module names.
    expect(find.text('2'), findsWidgets);

    // A module row: only that module's due cards, as many as it said.
    await _tap(t, controlByLabel(_engine));
    expect(find.byType(ReviewScreen), findsOneWidget);
    expect(spoken('2 left'), findsOneWidget);
    await _back(t);

    // The subject row: every due card of the subject.
    await _tap(t, controlByLabel('Review by module (3 due)'));
    await _tap(t, controlByLabel(_all));
    expect(find.byType(ReviewScreen), findsOneWidget);
    expect(spoken('3 left'), findsOneWidget);
  });

  testWidgets('desktop: the subject tile review glyph opens it', (t) async {
    await _home(t, const Size(1366, 1400));
    final tileReview = find.descendant(
      of: find.byType(SubjectTile),
      matching: controlByLabel('Review (3 due)'),
    );
    await _tap(t, tileReview);
    expect(controlByLabel(_engine), findsOneWidget);
    await _tap(t, controlByLabel(_fuel));
    expect(find.byType(ReviewScreen), findsOneWidget);
    expect(spoken('1 left'), findsOneWidget);
    expect(find.text('What ignites the mixture?'), findsOneWidget);
  });
}
