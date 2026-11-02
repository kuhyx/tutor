import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/focus/focus_models.dart';
import 'package:tutor/ui/focus_form.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/services.dart';
import '../support/ui.dart';

const FocusStatus _status = (
  day: '2026-11-02',
  active: null,
  projects: [],
  gates: [
    (id: 'leetcode', label: 'LeetCode', replaceable: true),
    (id: 'workout', label: 'Workout', replaceable: false),
  ],
  subjects: [(id: 'automation', title: 'Automation')],
);

void main() {
  testWidgets('create sends gates, subjects, sites and minutes', (t) async {
    final db = FakeRtdb();
    final stream = FakeStream();
    final s = services(db, stream);
    addTearDown(s.focus.dispose);
    await pumpScreen(t, FocusFormScreen(services: s, status: _status));
    final create = find.widgetWithText(FilledButton, 'Create');
    expect(t.widget<FilledButton>(create).onPressed, isNull);
    final fields = find.byType(TextField);
    await t.enterText(fields.at(0), 'HackerRank prep');
    await t.enterText(fields.last, 'hackerrank.com, leetcode.com');
    await t.tap(find.text('LeetCode'));
    await t.tap(find.text('Automation'));
    await t.pump();
    expect(
      t.widget<CheckboxListTile>(find.byType(CheckboxListTile).last).onChanged,
      isNull,
    );
    await t.tap(create);
    await t.pump(const Duration(milliseconds: 50));
    final (_, req) = lastRequest(db);
    expect(req['kind'], 'focus_create');
    final body = req['body'] as Map<String, dynamic>;
    expect(body['name'], 'HackerRank prep');
    expect(body['start'], '2026-11-02');
    expect(body['end'], '2026-11-05');
    expect(body['replaces'], ['leetcode']);
    expect(body['subjects'], ['automation']);
    expect(body['site_patterns'], ['hackerrank.com', 'leetcode.com']);
    expect(body['daily_minutes'], 120);
    expect(body['unlock_minutes'], 30);
    await answer(t, db, stream, data: {'id': 'hackerrank-prep'}, settle: false);
  });

  testWidgets('a refusal stays on the form with its text', (t) async {
    final db = FakeRtdb();
    final stream = FakeStream();
    final s = services(db, stream);
    addTearDown(s.focus.dispose);
    await pumpScreen(t, FocusFormScreen(services: s, status: _status));
    await t.enterText(find.byType(TextField).first, 'X');
    await t.pump();
    await t.tap(find.widgetWithText(FilledButton, 'Create'));
    await t.pump(const Duration(milliseconds: 50));
    await answer(
      t,
      db,
      stream,
      code: 'focus_refused',
      error: 'overlaps another project',
    );
    expect(find.textContaining('overlaps another project'), findsOneWidget);
    expect(find.byType(FocusFormScreen), findsOneWidget);
  });
}
