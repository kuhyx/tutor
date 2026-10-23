import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/home_screen.dart';

import '../support/fake_stream.dart';
import '../support/ui.dart';

/// Home with `stats.today` patched by [today] (the carry-over bank fields).
Future<void> _home(WidgetTester t, Map<String, Object> today) async {
  final db = fixtureDb();
  for (final MapEntry(:key, :value) in today.entries) {
    db.root = setAt(db.root, 'tutor/v1/stats/today/$key', value);
  }
  final s = await fixtureServices(db, FakeStream());
  await pumpScreen(
    t,
    HomeScreen(services: s, onSignedOut: () {}),
    size: const Size(412, 1400),
  );
}

void main() {
  testWidgets('Home shows the bank beside the credited counter', (t) async {
    await _home(t, {'banked': 25, 'prepaid': 15});
    expect(find.textContaining('Credited 23/60 min'), findsOneWidget);
    expect(find.text('Banked 25 min · prepaid 15'), findsOneWidget);
  });

  testWidgets('only prepaid is enough to show it', (t) async {
    await _home(t, {'banked': 0, 'prepaid': 30});
    expect(find.text('Banked 0 min · prepaid 30'), findsOneWidget);
  });

  testWidgets('an empty bank, or an older worker, shows nothing', (t) async {
    await _home(t, {'banked': 0, 'prepaid': 0});
    expect(find.textContaining('Banked'), findsNothing);
    await _home(t, {});
    expect(find.textContaining('Banked'), findsNothing);
  });
}
