// build-mobile-app R7: Focus and its project form fit one Pixel 6a screen;
// with the keyboard up the field typed in and Save stay visible.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/ui/focus_screen.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/fit.dart';
import '../support/services.dart';
import '../support/ui.dart';

const Map<String, Object> _project = {
  'id': 'hackerrank-prep',
  'name': 'HackerRank prep',
  'start': '2026-11-02',
  'end': '2026-11-05',
  'days_left': 4,
  'replaces': ['leetcode', 'reading'],
  'daily_minutes': 120,
  'unlock_minutes': 30,
  'subjects': ['automation'],
  'site_patterns': ['hackerrank.com'],
};

Map<String, Object?> _status({required bool active}) => {
  'day': '2026-11-02',
  'active': active ? {..._project, 'minutes': 42} : null,
  'projects': [_project],
  'gates': [
    for (final g in ['leetcode', 'reading', 'anki', 'duolingo', 'piano'])
      {'id': g, 'label': g, 'replaceable': true},
    {'id': 'workout', 'label': 'Workout', 'replaceable': false},
  ],
  'subjects': [
    {'id': 'automation', 'title': 'Automation'},
    {'id': 'car', 'title': 'How a car works'},
  ],
};

void main() {
  Future<void> open(
    WidgetTester t,
    double scale, {
    bool active = true,
    bool running = false,
  }) async {
    pixelView(t, scale: scale);
    final db = FakeRtdb();
    final stream = FakeStream();
    final kv = MemoryKv();
    if (running) {
      final last = DateTime.now().millisecondsSinceEpoch - 60000;
      await kv.set(
        'focus.timer',
        jsonEncode({'running': true, 'last': last, 'counted': 0}),
      );
    }
    final s = services(db, stream, kv: kv);
    addTearDown(s.focus.dispose);
    await pumpFit(t, FocusScreen(services: s), settle: false);
    await answer(t, db, stream, data: _status(active: active));
  }

  fitTest('Focus, no project', (t, scale) async {
    await open(t, scale, active: false);
    expectFits(t, state: 'none');
    expectReachable(t, find.text('New project'));
  });

  fitTest('Focus running', (t, scale) async {
    await open(t, scale, running: true);
    expectFits(t, state: 'running');
    expectReachable(t, find.text('Stop'));
    // Stops the timer, as focus_screen_test does (no pending timers).
    await t.tap(find.text('Stop'));
    await t.pump(const Duration(milliseconds: 50));
  });

  fitTest('Focus project and form', (t, scale) async {
    await open(t, scale);
    expectFits(t, state: 'project');
    expectReachable(t, find.text('Start'));
    expectReachable(t, find.text('Edit'));
    await t.tap(find.text('Edit'));
    await t.pumpAndSettle();
    expectFits(t, state: 'form');
    expectReachable(t, find.text('Save'));
    for (final label in ['Name', 'Minutes per day', 'Sites', 'Work URL']) {
      final field = find.ancestor(
        of: find.textContaining(label),
        matching: find.byType(TextField),
      );
      await pageTo(t, field);
      await t.tap(field.hitTestable().first);
      pixelView(t, scale: scale, keyboard: fitKeyboard);
      await t.pumpAndSettle();
      expectFits(t, state: '$label + keyboard');
      expectReachable(t, find.text('Save'), state: label);
      pixelView(t, scale: scale);
      await t.pumpAndSettle();
    }
  });
}
