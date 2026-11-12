import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/progress_screen.dart';

import '../support/fake_stream.dart';
import '../support/learn_finders.dart';
import '../support/ui.dart';

void main() {
  testWidgets('charts, day table, module recall', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      ProgressScreen(services: s),
      size: const Size(1366, 2400),
    );
    expect(spoken('Credited minutes per day'), findsOneWidget);
    expect(find.text('2026-10-12'), findsOneWidget);
    expect(spoken('recall 85%'), findsOneWidget);
    expect(spokenHas('Reviewed: every card'), findsWidgets);
  });

  testWidgets('no days yet; unreachable', (t) async {
    final db = fixtureDb();
    db.root = setAt(db.root, 'tutor/v1-e2e/stats/days', null);
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, ProgressScreen(services: s));
    expect(spokenHas('No days yet'), findsOneWidget);
    db.offline = true;
    await pumpScreen(t, ProgressScreen(services: s, key: UniqueKey()));
    expect(cueHas('Could not load'), findsOneWidget);
  });
}
