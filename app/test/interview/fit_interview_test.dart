// build-mobile-app R7: the interview focus screen and the create form with
// the interview part open fit one Pixel 6a screen: no vertical scroll, every
// icon reachable, with the status bar, nav inset and the keyboard.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/focus/focus_models.dart';
import 'package:tutor/ui/focus_form.dart';
import 'package:tutor/ui/focus_screen.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/fit.dart';
import '../support/services.dart';
import '../support/ui.dart';
import '_data.dart';
import '_fakes.dart';

Map<String, Object?> _status({bool errors = false}) => statusOf(
  interviewProject(
    // A long project: many weekends, so many trip and phone milestones.
    milestones: [
      ms('rules', '2026-11-10T23:59:00', errors ? 'missed' : 'pending'),
      for (final sat in ['2026-11-14', '2026-11-21', '2026-11-28'])
        ms('trip_ask:$sat', '2026-11-12T23:59:00', 'pending'),
      for (final sat in ['2026-11-14', '2026-11-21', '2026-11-28'])
        ms('phone:$sat', '2026-11-13T12:00:00', 'pending'),
      ms('mock', '2026-11-18T23:59:00', 'pending'),
      ms('slot', '2026-11-19T12:00:00', 'pending'),
    ],
  ),
);

const FocusStatus _formStatus = (
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
  fitTest('Focus screen with the interview row', (t, scale) async {
    pixelView(t, scale: scale);
    final db = FakeRtdb();
    final stream = FakeStream();
    final s = services(db, stream);
    addTearDown(s.focus.dispose);
    await pumpFit(t, FocusScreen(services: s), settle: false);
    await answer(t, db, stream, data: _status());
    expectFits(t, state: 'interview');
    for (final n in ['rules', 'trip', 'phone', 'clock', 'mock', 'slot']) {
      expectReachable(t, find.byKey(ValueKey('ms:$n')), state: n);
    }
    expectReachable(t, find.text('Start'));
  });

  fitTest('Focus screen with the error state shown', (t, scale) async {
    pixelView(t, scale: scale);
    final db = FakeRtdb();
    final stream = FakeStream();
    final s = services(db, stream);
    addTearDown(s.focus.dispose);
    final prompts = FakePrompts()..score = 5;
    await pumpFit(t, FocusScreen(services: s, prompts: prompts), settle: false);
    await answer(t, db, stream, data: _status(errors: true));
    await t.tap(find.byKey(const ValueKey('ms:mock')));
    await sent(t);
    await answer(
      t,
      db,
      stream,
      code: 'focus_refused',
      error: 'refused',
      settle: false,
    );
    await sent(t);
    expect(find.byKey(const ValueKey('interview-error')), findsOneWidget);
    expectFits(t, state: 'interview error');
    expectReachable(t, find.byKey(const ValueKey('interview-error')));
    expectReachable(t, find.text('Start'));
  });

  fitTest('Create form, interview part open', (t, scale) async {
    pixelView(t, scale: scale);
    final db = FakeRtdb();
    final stream = FakeStream();
    final s = services(db, stream);
    addTearDown(s.focus.dispose);
    final prompts = FakePrompts()
      ..dateTime = DateTime(2026, 11, 20, 10)
      ..range = (start: DateTime(2026, 11, 14), end: DateTime(2026, 11, 15));
    await pumpFit(
      t,
      FocusFormScreen(services: s, status: _formStatus, prompts: prompts),
    );
    final toggle = find.byKey(const ValueKey('interview-toggle'));
    await pageTo(t, toggle);
    await t.tap(toggle);
    await t.pumpAndSettle();
    expectFits(t, state: 'form toggled');
    for (final k in ['interview-test-at', 'interview-trip-add']) {
      final f = find.byKey(ValueKey(k));
      await pageTo(t, f);
      expectReachable(t, f, state: k);
      await t.tap(f);
      await t.pumpAndSettle();
    }
    expectFits(t, state: 'form with trip');
    expectReachable(t, find.text('Create'));
    final url = find.descendant(
      of: find.byKey(const ValueKey('interview-url')),
      matching: find.byType(TextField),
    );
    await pageTo(t, url);
    await t.tap(url);
    pixelView(t, scale: scale, keyboard: fitKeyboard);
    await t.pumpAndSettle();
    expectFits(t, state: 'url + keyboard');
    expectReachable(t, find.text('Create'), state: 'url');
  });
}
