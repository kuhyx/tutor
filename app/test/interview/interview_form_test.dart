import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/focus/focus_models.dart';
import 'package:tutor/ui/focus_form.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/services.dart';
import '../support/ui.dart';
import '_fakes.dart';

const FocusStatus _status = (
  day: '2026-11-10',
  active: null,
  projects: [],
  gates: [
    (id: 'leetcode', label: 'LeetCode', replaceable: true),
    (id: 'workout', label: 'Workout', replaceable: false),
  ],
  subjects: [(id: 'automation', title: 'Automation')],
);

void main() {
  late FakeRtdb db;
  late FakeStream stream;
  late FakePrompts prompts;

  Future<void> open(WidgetTester t) async {
    db = FakeRtdb();
    stream = FakeStream();
    prompts = FakePrompts();
    final s = services(db, stream);
    addTearDown(s.focus.dispose);
    await pumpScreen(
      t,
      FocusFormScreen(services: s, status: _status, prompts: prompts),
    );
  }

  Finder key(String k) => find.byKey(ValueKey(k));

  Future<void> tapKey(WidgetTester t, String k) async {
    await t.ensureVisible(key(k));
    await t.tap(key(k));
    await t.pump();
  }

  FilledButton create(WidgetTester t) =>
      t.widget<FilledButton>(find.widgetWithText(FilledButton, 'Create'));

  testWidgets('the interview part is hidden until its toggle is on', (t) async {
    await open(t);
    expect(key('interview-toggle'), findsOneWidget);
    for (final k in [
      'interview-test-at',
      'interview-url',
      'interview-trip-add',
      'interview-no-trip',
    ]) {
      expect(key(k), findsNothing, reason: k);
    }
    await tapKey(t, 'interview-toggle');
    for (final k in [
      'interview-test-at',
      'interview-url',
      'interview-trip-add',
      'interview-no-trip',
    ]) {
      expect(key(k), findsOneWidget, reason: k);
    }
  });

  testWidgets('the interview part adds no words of its own', (t) async {
    await open(t);
    await tapKey(t, 'interview-toggle');
    for (final k in [
      'interview-toggle',
      'interview-test-at',
      'interview-trip-add',
      'interview-no-trip',
    ]) {
      expect(
        find.descendant(of: key(k), matching: find.byType(Text)),
        findsNothing,
        reason: k,
      );
    }
  });

  testWidgets('create needs a test time and a trip answer', (t) async {
    await open(t);
    await t.enterText(find.byType(TextField).first, 'Acme interview');
    await tapKey(t, 'interview-toggle');
    expect(create(t).onPressed, isNull, reason: 'no test time yet');

    prompts.dateTime = DateTime(2026, 11, 20, 10);
    await tapKey(t, 'interview-test-at');
    expect(create(t).onPressed, isNull, reason: 'no trips answer yet');

    await tapKey(t, 'interview-no-trip');
    expect(create(t).onPressed, isNotNull);
  });

  testWidgets('trips and no-trip exclude each other', (t) async {
    await open(t);
    await tapKey(t, 'interview-toggle');
    await tapKey(t, 'interview-no-trip');
    expect(t.widget<Switch>(key('interview-no-trip')).value, isTrue);

    prompts.range = (
      start: DateTime(2026, 11, 14),
      end: DateTime(2026, 11, 15),
    );
    await tapKey(t, 'interview-trip-add');
    expect(key('interview-trip:2026-11-14'), findsOneWidget);
    expect(
      t.widget<Switch>(key('interview-no-trip')).value,
      isFalse,
      reason: 'adding a trip clears no-trip',
    );

    await tapKey(t, 'interview-no-trip');
    expect(
      key('interview-trip:2026-11-14'),
      findsNothing,
      reason: 'no-trip drops the trips',
    );
  });

  testWidgets('a trip can be removed again before sending', (t) async {
    await open(t);
    await tapKey(t, 'interview-toggle');
    prompts.range = (
      start: DateTime(2026, 11, 14),
      end: DateTime(2026, 11, 15),
    );
    await tapKey(t, 'interview-trip-add');
    await tapKey(t, 'interview-trip:2026-11-14');
    expect(key('interview-trip:2026-11-14'), findsNothing);
  });

  testWidgets('trip dates are bounded by today and the test day', (t) async {
    await open(t);
    await tapKey(t, 'interview-toggle');
    prompts.dateTime = DateTime(2026, 11, 20, 10);
    await tapKey(t, 'interview-test-at');
    await tapKey(t, 'interview-trip-add');
    expect(prompts.bounds!.first, DateTime(2026, 11, 10));
    expect(prompts.bounds!.last, DateTime(2026, 11, 20));
  });

  testWidgets('create sends an interview: end = test day, trips, url', (
    t,
  ) async {
    await open(t);
    await t.enterText(find.byType(TextField).first, 'Acme interview');
    await t.tap(find.text('LeetCode'));
    await tapKey(t, 'interview-toggle');
    await t.enterText(
      find.descendant(
        of: key('interview-url'),
        matching: find.byType(TextField),
      ),
      'https://app.codility.com/c/acme',
    );
    prompts
      ..dateTime = DateTime(2026, 11, 20, 10)
      ..range = (start: DateTime(2026, 11, 14), end: DateTime(2026, 11, 15));
    await tapKey(t, 'interview-test-at');
    await tapKey(t, 'interview-trip-add');
    await t.ensureVisible(find.widgetWithText(FilledButton, 'Create'));
    await t.tap(find.widgetWithText(FilledButton, 'Create'));
    await t.pump(const Duration(milliseconds: 50));
    final (_, req) = lastRequest(db);
    expect(req['kind'], 'focus_create');
    final body = req['body'] as Map<String, dynamic>;
    expect(body['kind'], 'interview');
    expect(body['name'], 'Acme interview');
    expect(body['start'], '2026-11-10');
    expect(body['end'], '2026-11-20');
    expect(body['test_at'], '2026-11-20T10:00');
    expect(body['invite_url'], 'https://app.codility.com/c/acme');
    expect(body['trips'], [
      {'start': '2026-11-14', 'end': '2026-11-15'},
    ]);
    expect(body.containsKey('no_trip'), isFalse);
    expect(body['daily_minutes'], 30);
    expect(body['replaces'], ['leetcode']);
    await answer(t, db, stream, data: {'id': 'acme-interview'}, settle: false);
  });

  testWidgets('create with no trip sends no_trip:true and no list', (t) async {
    await open(t);
    await t.enterText(find.byType(TextField).first, 'Acme interview');
    await tapKey(t, 'interview-toggle');
    prompts.dateTime = DateTime(2026, 11, 20, 10);
    await tapKey(t, 'interview-test-at');
    await tapKey(t, 'interview-no-trip');
    await t.ensureVisible(find.widgetWithText(FilledButton, 'Create'));
    await t.tap(find.widgetWithText(FilledButton, 'Create'));
    await t.pump(const Duration(milliseconds: 50));
    final body = lastRequest(db).$2['body'] as Map<String, dynamic>;
    expect(body['no_trip'], isTrue);
    expect(body.containsKey('trips'), isFalse);
    await answer(t, db, stream, data: {'id': 'acme-interview'}, settle: false);
  });

  testWidgets('a bad invite url blocks create; empty is fine', (t) async {
    await open(t);
    await t.enterText(find.byType(TextField).first, 'Acme interview');
    await tapKey(t, 'interview-toggle');
    prompts.dateTime = DateTime(2026, 11, 20, 10);
    await tapKey(t, 'interview-test-at');
    await tapKey(t, 'interview-no-trip');
    final url = find.descendant(
      of: key('interview-url'),
      matching: find.byType(TextField),
    );
    await t.enterText(url, 'not a url');
    await t.pump();
    expect(create(t).onPressed, isNull);
    await t.enterText(url, '');
    await t.pump();
    expect(create(t).onPressed, isNotNull);
  });

  testWidgets('switching the toggle off sends a plain focus project', (
    t,
  ) async {
    await open(t);
    await t.enterText(find.byType(TextField).first, 'Plain');
    await tapKey(t, 'interview-toggle');
    await tapKey(t, 'interview-toggle');
    await t.ensureVisible(find.widgetWithText(FilledButton, 'Create'));
    await t.tap(find.widgetWithText(FilledButton, 'Create'));
    await t.pump(const Duration(milliseconds: 50));
    final body = lastRequest(db).$2['body'] as Map<String, dynamic>;
    expect(body.containsKey('kind'), isFalse);
    expect(body['daily_minutes'], 120);
    await answer(t, db, stream, data: {'id': 'plain'}, settle: false);
  });
}
