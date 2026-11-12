import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/focus_form.dart';
import 'package:tutor/ui/focus_screen.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/no_words.dart';
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

Map<String, Object?> _status({
  bool active = true,
  int minutes = 42,
  int? unbacked,
}) => {
  'day': '2026-11-02',
  'active': active
      ? {..._project, 'minutes': minutes, 'unbacked_minutes': ?unbacked}
      : null,
  'projects': [_project],
  'gates': [
    {'id': 'leetcode', 'label': 'LeetCode', 'replaceable': true},
    {'id': 'reading', 'label': 'Reading', 'replaceable': true},
    {'id': 'workout', 'label': 'Workout', 'replaceable': false},
  ],
  'subjects': [
    {'id': 'automation', 'title': 'Automation'},
  ],
};

void main() {
  late FakeRtdb db;
  late FakeStream stream;

  Future<void> open(
    WidgetTester t, {
    bool active = true,
    bool autoStart = false,
    bool running = false,
    int minutes = 42,
    int? unbacked,
    int lastAgoMs = 60000,
  }) async {
    db = FakeRtdb();
    stream = FakeStream();
    final kv = MemoryKv();
    if (running) {
      final last = DateTime.now().millisecondsSinceEpoch - lastAgoMs;
      await kv.set(
        'focus.timer',
        jsonEncode({'running': true, 'last': last, 'counted': 0}),
      );
    }
    final s = services(db, stream, kv: kv);
    addTearDown(s.focus.dispose);
    await pumpScreen(
      t,
      FocusScreen(services: s, autoStart: autoStart),
      settle: false,
    );
    await answer(
      t,
      db,
      stream,
      data: _status(active: active, minutes: minutes, unbacked: unbacked),
    );
  }

  int statusRequests() {
    final reqs = getAt(db.root, 'tutor/v1-e2e/requests') as Map<String, dynamic>?;
    return [
      for (final r in (reqs ?? {}).values)
        if (((r as Map<String, dynamic>)['req'] as Map)['kind'] ==
            'focus_status')
          r,
    ].length;
  }

  List<Object?> focusEvents() {
    final reqs = getAt(db.root, 'tutor/v1-e2e/requests') as Map<String, dynamic>?;
    return [
      for (final r in (reqs ?? {}).values)
        if (((r as Map<String, dynamic>)['req'] as Map)['kind'] ==
            'focus_event')
          (r['req'] as Map)['body'],
    ];
  }

  testWidgets('shows the project, ring, off and kept gates', (t) async {
    await open(t);
    expect(find.text('HackerRank prep'), findsOneWidget);
    expect(find.text('4 days left'), findsOneWidget);
    expect(find.text('42'), findsOneWidget);
    expect(find.text('120'), findsOneWidget);
    expect(find.text('LeetCode'), findsOneWidget);
    expect(find.text('Workout'), findsOneWidget);
    expect(find.text('Start'), findsOneWidget);
  });

  testWidgets('overtime shows the real minutes and what is banked', (t) async {
    await open(t, minutes: 121);
    expect(find.text('121'), findsOneWidget);
    expect(find.text('120'), findsOneWidget);
    expect(find.text('(+1 banked)'), findsOneWidget);
  });

  testWidgets('the bank shown is capped at the 60 the server banks', (t) async {
    await open(t, minutes: 300);
    expect(find.text('(+60 banked)'), findsOneWidget);
  });

  testWidgets('unbacked minutes show under the ring', (t) async {
    await open(t, unbacked: 12);
    final mark = find.byKey(const ValueKey('unbacked'));
    expect(mark, findsOneWidget);
    expect(
      find.descendant(
        of: mark,
        matching: find.byIcon(Icons.timer_off_outlined),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(of: mark, matching: find.text('12')),
      findsOneWidget,
    );
    expect(
      find.bySemanticsLabel('12 min unbacked (not counted)'),
      findsOneWidget,
    );
    expect(find.textContaining('unbacked'), findsNothing);
    expectNoWords(t, 'focus with unbacked minutes');
  });

  testWidgets('no unbacked minutes, no unbacked line', (t) async {
    await open(t, unbacked: 0);
    expect(find.byKey(const ValueKey('unbacked')), findsNothing);
  });

  testWidgets('an older server without the field shows no line', (t) async {
    await open(t);
    expect(find.byKey(const ValueKey('unbacked')), findsNothing);
  });

  testWidgets('no project, no unbacked line', (t) async {
    await open(t, active: false, unbacked: 5);
    expect(find.byKey(const ValueKey('unbacked')), findsNothing);
  });

  testWidgets('the ring moves on server figures, not the running clock', (
    t,
  ) async {
    // 4 min 59 s into a run: the client clock reaches 5 min a second after
    // the status loads; the ring must stay at the server's 42.
    await open(t, running: true, lastAgoMs: 299000);
    await t.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 1500)),
    );
    await t.pump(const Duration(seconds: 2));
    expect(find.text('42'), findsOneWidget);
    expect(find.text('43'), findsNothing);
    await t.tap(find.text('Stop'));
    await t.pump(const Duration(milliseconds: 50));
  });

  testWidgets('Start refreshes the status', (t) async {
    await open(t);
    final before = statusRequests();
    await t.tap(find.text('Start'));
    await t.pump(const Duration(milliseconds: 50));
    expect(statusRequests(), before + 1);
    await t.tap(find.text('Stop'));
    await t.pump(const Duration(milliseconds: 50));
  });

  testWidgets('no overtime, no bank line', (t) async {
    await open(t);
    expect(find.textContaining('banked'), findsNothing);
  });

  testWidgets('Start queues a start tap with its time; Stop ends it', (
    t,
  ) async {
    await open(t);
    await t.tap(find.text('Start'));
    await t.pump(const Duration(milliseconds: 50));
    expect(find.text('Stop'), findsOneWidget);
    // The status is asked again after the tap, so it is not the last request.
    final body = focusEvents().single! as Map<String, dynamic>;
    expect(body['event'], 'start');
    expect(body['platform'], 'phone');
    expect(body['ts'], isA<int>());
    await t.tap(find.text('Stop'));
    await t.pump(const Duration(milliseconds: 50));
    expect(find.text('Start'), findsOneWidget);
  });

  testWidgets('Edit opens the form on the active project', (t) async {
    await open(t);
    await t.tap(find.text('Edit'));
    await t.pumpAndSettle();
    expect(find.byType(FocusFormScreen), findsOneWidget);
    expect(find.text('hackerrank.com'), findsOneWidget);
    expect(find.text('Save'), findsOneWidget);
  });

  testWidgets('no project: only New project', (t) async {
    await open(t, active: false);
    expect(find.text('No focus project'), findsOneWidget);
    expect(find.text('New project'), findsOneWidget);
    expect(find.text('Start'), findsNothing);
  });

  testWidgets('autoStart starts a stopped timer on an active project', (
    t,
  ) async {
    await open(t, autoStart: true);
    await t.pump(const Duration(milliseconds: 50));
    expect(find.text('Stop'), findsOneWidget);
    expect(focusEvents().length, 1);
    expect((focusEvents().single! as Map)['event'], 'start');
    await t.tap(find.text('Stop')); // no timer may outlive the test
    await t.pump(const Duration(milliseconds: 50));
  });

  testWidgets('autoStart leaves a running timer alone', (t) async {
    await open(t, autoStart: true, running: true);
    await t.pump(const Duration(milliseconds: 50));
    expect(find.text('Stop'), findsOneWidget);
    expect(focusEvents(), isEmpty);
    await t.tap(find.text('Stop'));
    await t.pump(const Duration(milliseconds: 50));
  });

  testWidgets('autoStart does nothing without an active project', (t) async {
    await open(t, active: false, autoStart: true);
    await t.pump(const Duration(milliseconds: 50));
    expect(focusEvents(), isEmpty);
  });

  testWidgets('without autoStart the timer stays stopped', (t) async {
    await open(t);
    await t.pump(const Duration(milliseconds: 50));
    expect(find.text('Start'), findsOneWidget);
    expect(focusEvents(), isEmpty);
  });

  testWidgets('fits a Pixel 6a screen with no scrolling', (t) async {
    t.view
      ..physicalSize = const Size(1080, 2400)
      ..devicePixelRatio = 2.625
      ..padding = const FakeViewPadding(top: 132, bottom: 63);
    addTearDown(t.view.reset);
    await open(t);
    expect(find.byType(Scrollable), findsNothing);
    final start = t.getRect(find.text('Start'));
    expect(start.bottom, lessThan(2400 / 2.625 - 63 / 2.625));
  });
}
