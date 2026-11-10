import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/focus/focus_models.dart';
import 'package:tutor/ui/focus_form.dart';
import 'package:tutor/ui/numeric_date_picker.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
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

const FocusProject _edited = (
  id: 'hr',
  name: 'HR prep',
  start: '2026-11-01',
  end: '2026-11-06',
  daysLeft: 5,
  replaces: ['leetcode'],
  dailyMinutes: 90,
  unlockMinutes: 20,
  subjects: ['automation'],
  sitePatterns: ['a.com', 'b.com'],
  workUrl: 'https://a.com/start',
  minutes: 10,
  unbackedMinutes: 0,
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
    await t.enterText(
      find.widgetWithText(TextField, 'Sites, comma separated'),
      'hackerrank.com, leetcode.com',
    );
    await t.enterText(
      find.widgetWithText(TextField, 'Work URL'),
      'https://www.hackerrank.com/dashboard',
    );
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
    expect(body['work_url'], 'https://www.hackerrank.com/dashboard');
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
    expect(cueOfKind(CueKind.error), findsOneWidget);
    expect(find.byType(FocusFormScreen), findsOneWidget);
  });

  testWidgets('edit is prefilled and sends focus_update with its id', (
    t,
  ) async {
    final db = FakeRtdb();
    final stream = FakeStream();
    final s = services(db, stream);
    addTearDown(s.focus.dispose);
    await pumpScreen(
      t,
      FocusFormScreen(services: s, status: _status, edit: _edited),
    );
    expect(find.text('HR prep'), findsOneWidget);
    expect(find.text('90'), findsOneWidget);
    expect(find.text('a.com, b.com'), findsOneWidget);
    expect(find.text('https://a.com/start'), findsOneWidget);
    expect(find.text('2026-11-06'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Create'), findsNothing);
    // A started project's start date is fixed.
    await t.tap(find.text('2026-11-01'));
    await t.pump();
    expect(find.byType(NumericDatePicker), findsNothing);
    await t.enterText(find.byType(TextField).first, 'HR prep 2');
    await t.tap(find.text('Automation'));
    await t.pump();
    await t.tap(find.widgetWithText(FilledButton, 'Save'));
    await t.pump(const Duration(milliseconds: 50));
    final (_, req) = lastRequest(db);
    expect(req['kind'], 'focus_update');
    final body = req['body'] as Map<String, dynamic>;
    expect(body['id'], 'hr');
    expect(body['name'], 'HR prep 2');
    expect(body['start'], '2026-11-01');
    expect(body['end'], '2026-11-06');
    expect(body['replaces'], ['leetcode']);
    expect(body['subjects'], isEmpty);
    expect(body['site_patterns'], ['a.com', 'b.com']);
    expect(body['work_url'], 'https://a.com/start');
    expect(body['daily_minutes'], 90);
    expect(body['unlock_minutes'], 20);
    await answer(t, db, stream, data: {'id': 'hr'}, settle: false);
  });

  testWidgets('a work URL that is not http(s) blocks saving; empty is fine', (
    t,
  ) async {
    final db = FakeRtdb();
    final stream = FakeStream();
    final s = services(db, stream);
    addTearDown(s.focus.dispose);
    await pumpScreen(
      t,
      FocusFormScreen(services: s, status: _status, edit: _edited),
    );
    final save = find.widgetWithText(FilledButton, 'Save');
    final url = find.widgetWithText(TextField, 'Work URL');
    for (final bad in ['javascript:alert(1)', 'hackerrank.com', 'https://']) {
      await t.enterText(url, bad);
      await t.pump();
      expect(t.widget<FilledButton>(save).onPressed, isNull, reason: bad);
    }
    await t.enterText(url, '');
    await t.pump();
    expect(t.widget<FilledButton>(save).onPressed, isNotNull);
    await t.tap(save);
    await t.pump(const Duration(milliseconds: 50));
    final (_, req) = lastRequest(db);
    expect((req['body'] as Map<String, dynamic>)['work_url'], '');
  });

  testWidgets('a project that has not started can move its start', (t) async {
    final db = FakeRtdb();
    final stream = FakeStream();
    final s = services(db, stream);
    addTearDown(s.focus.dispose);
    const later = (
      id: 'hr',
      name: 'HR',
      start: '2026-11-04',
      end: '2026-11-06',
      daysLeft: 3,
      replaces: <String>[],
      dailyMinutes: 60,
      unlockMinutes: 0,
      subjects: <String>[],
      sitePatterns: <String>[],
      workUrl: '',
      minutes: 0,
      unbackedMinutes: 0,
    );
    await pumpScreen(
      t,
      FocusFormScreen(services: s, status: _status, edit: later),
    );
    await t.tap(find.text('2026-11-04'));
    await t.pumpAndSettle();
    expect(find.byType(NumericDatePicker), findsOneWidget);
  });
}
