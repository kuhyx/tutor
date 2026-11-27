// Phone (narrow) Progress: chips, All days and subject sheets; the empty
// states. Split from fit_flows_test.dart (250-line gate).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/progress_screen.dart';

import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/learn_finders.dart';
import '../support/services.dart';
import '../support/ui.dart';

const _phone = Size(412, 900);

Future<void> _tap(WidgetTester t, Finder f) async {
  await t.tap(f);
  await t.pumpAndSettle();
}

void main() {
  testWidgets('Progress: chips, All days, a subject sheet', (t) async {
    final s = await fixtureServices(fixtureDb(), FakeStream());
    await pumpScreen(t, ProgressScreen(services: s), size: _phone);
    expect(find.bySemanticsLabel(RegExp('^min per day, 7 days')), findsOne);
    await _tap(t, chipSpoken('Taught'));
    expect(find.bySemanticsLabel(RegExp('^cards per day')), findsOne);
    await _tap(t, controlByLabel('All days'));
    expect(find.text('2026-10-12'), findsOneWidget);
    expect(find.text('2026-09-29'), findsOneWidget);
    await t.tapAt(const Offset(10, 10));
    await t.pumpAndSettle();
    await _tap(t, find.byKey(const ValueKey('subject-stat-0')));
    expect(bySpoken('recall 85%'), findsWidgets);
    expect(bySpoken('reviewed', prefix: true), findsWidgets);
    expect(find.text('Brakes'), findsOneWidget);
  });

  testWidgets('Progress: no days yet', (t) async {
    final db = fixtureDb();
    db.root = setAt(db.root, 'tutor/v1-e2e/stats/days', null);
    final s = await fixtureServices(db, FakeStream());
    await pumpScreen(t, ProgressScreen(services: s), size: _phone);
    expect(spokenHas('No days yet'), findsOneWidget);
    expect(controlByLabel('All days'), findsNothing);
  });

  testWidgets('Progress: no approved plans yet', (t) async {
    final s = services(fixtureDb(), FakeStream()); // nothing cached
    await pumpScreen(t, ProgressScreen(services: s), size: _phone);
    expect(spoken('No approved plans yet.'), findsOneWidget);
  });
}
