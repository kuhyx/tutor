// Home ⋮ -> "New cards per day": shows the effective value (25 by default),
// saves 1..200 as a `new_cap` log event that syncs to the PC.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/home_screen.dart';

import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/services.dart';
import '../support/ui.dart';

void main() {
  testWidgets('New cards per day: 25, then saved as a new_cap event', (
    t,
  ) async {
    final db = fixtureDb();
    final s = await fixtureServices(db, FakeStream());
    await pumpScreen(t, HomeScreen(services: s, onSignedOut: () {}));
    Future<void> open() async {
      await t.tap(bySpoken('More'));
      await t.pumpAndSettle();
      await t.tap(bySpoken('New cards per day'));
      await t.pumpAndSettle();
    }

    await open();
    final field = find.descendant(
      of: find.byType(AlertDialog),
      matching: find.byType(TextField),
    );
    expect(t.widget<TextField>(field).controller!.text, '25');

    await t.enterText(field, '0');
    await t.tap(controlByLabel('Save'));
    await t.pumpAndSettle();
    expect(cueLabelled('A number from 1 to 200'), findsOneWidget);
    await t.enterText(field, '201');
    await t.tap(controlByLabel('Save'));
    await t.pumpAndSettle();
    expect(cueLabelled('A number from 1 to 200'), findsOneWidget);

    await t.enterText(field, '40');
    await t.tap(controlByLabel('Save'));
    await t.pumpAndSettle();
    expect(controlByLabel('Save'), findsNothing); // closed
    final caps = (await s.events.all()).map((e) => e.event);
    expect(caps.whereType<NewCapEvent>().map((e) => e.n), [40]);
    // Synced: under this device's log.
    final log = getAt(db.root, 'tutor/v1-e2e/log/$testDev')! as Map;
    expect(log.values.single, containsPair('k', 'new_cap'));
    expect(log.values.single, containsPair('n', 40));

    await open();
    expect(t.widget<TextField>(field).controller!.text, '40');
  });
}
