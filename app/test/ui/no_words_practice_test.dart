// textgate guard, practice screens: the mock test, coach and the focus screen
// paint no app words in their working states (the entry states are in
// no_words_test.dart; SQL drills and lessons: no_words_sql_test.dart).
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/mock/mock_entry.dart';
import 'package:tutor/mock/mock_result_screen.dart';
import 'package:tutor/mock/mock_start_screen.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/ui/coach/coach_picker.dart';
import 'package:tutor/ui/coach/coach_postmortem.dart';
import 'package:tutor/ui/focus_screen.dart';

import '../coach/coach_fixtures.dart' as c;
import '../mock/mock_fixtures.dart';
import '../mock/mock_support.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/no_words.dart';
import '../support/services.dart';
import '../support/ui.dart';
import 'coach/coach_support.dart' show CoachRig;

const _focusProject = <String, Object>{
  'id': 'prep',
  'name': 'HackerRank prep',
  'start': '2026-11-02',
  'end': '2026-11-05',
  'days_left': 4,
  'replaces': ['leetcode'],
  'daily_minutes': 120,
  'unlock_minutes': 30,
  'subjects': ['automation'],
  'site_patterns': ['hackerrank.com'],
};

void main() {
  group('mock test', () {
    late Rig rig;
    setUp(() => rig = Rig());

    testWidgets('start screen (reached, not loading)', (t) async {
      await pumpScreen(
        t,
        MockStartScreen(services: rig.s, links: rig.links),
        size: phone,
      );
      expect(find.byType(MockStartScreen), findsOneWidget);
      expectNoWords(t, 'mock start');
    });

    testWidgets('start screen failure cue', (t) async {
      await pumpScreen(
        t,
        MockStartScreen(services: rig.s, links: rig.links),
        size: phone,
        settle: false,
      );
      await t.tap(find.byKey(const ValueKey('start')));
      await sent(t);
      await answer(t, rig.db, rig.stream, data: const {'tasks': 5});
      expectNoWords(t, 'mock start problem');
    });

    testWidgets('entry opens the start screen', (t) async {
      await pumpScreen(
        t,
        Builder(
          builder: (c) => TextButton(
            onPressed: () => unawaited(openMock(c, rig.s, links: rig.links)),
            child: const Text('x'),
          ),
        ),
        size: phone,
      );
      await t.tap(find.byType(TextButton));
      await t.pumpAndSettle();
      expect(find.byType(MockStartScreen), findsOneWidget);
    });

    testWidgets('test running: notes, chips, question, options', (t) async {
      await rig.pumpTest(t);
      expectNoWords(t, 'mock question');
      await t.tap(find.byKey(const ValueKey('opt-1')));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const ValueKey('nav-3')));
      await t.pump();
      expectNoWords(t, 'mock sql task');
      await t.tap(find.byKey(const ValueKey('finish')));
      await t.pumpAndSettle();
      expectNoWords(t, 'mock finish dialog');
    });

    testWidgets('result with details', (t) async {
      final m = rig.session()..finished(resultData);
      await pumpScreen(
        t,
        MockResultScreen(services: rig.s, session: m, links: rig.links),
        size: phone,
      );
      expectNoWords(t, 'mock result');
      await t.tap(find.byKey(const ValueKey('item-q1')));
      await t.pumpAndSettle();
      expectNoWords(t, 'mock result opened');
    });
  });

  group('coach', () {
    late CoachRig rig;
    setUp(() => rig = CoachRig());

    testWidgets('chat, reply with a snippet, a failed run', (t) async {
      await rig.open(t);
      expectNoWords(t, 'coach chat');
      await rig.say(t, 'two pointers');
      await rig.reply(t, c.turnData);
      expectNoWords(t, 'coach reply');
      await rig.tap(t, 'reveal');
      expectNoWords(t, 'coach reveal dialog');
      await t.tap(find.byKey(const ValueKey('reveal-cancel')));
      await t.pumpAndSettle();
    });

    testWidgets('a failed turn is an error cue', (t) async {
      await rig.open(t);
      await rig.say(t, 'hello');
      await rig.reply(t, const {}, code: 'model_error');
      expectNoWords(t, 'coach turn failed');
    });

    testWidgets('SQL problem opens', (t) async {
      await rig.open(t, first: c.sqlOpenData);
      expectNoWords(t, 'coach sql');
    });
  });

  group('coach lists', () {
    late FakeRtdb db;
    late FakeStream stream;

    testWidgets('picker with due, recent and clusters', (t) async {
      db = FakeRtdb();
      stream = FakeStream();
      await pumpScreen(
        t,
        CoachPickerScreen(services: services(db, stream)),
        settle: false,
      );
      await answer(t, db, stream, data: c.listData);
      expectNoWords(t, 'coach picker');
    });

    testWidgets('post-mortem cards', (t) async {
      db = FakeRtdb();
      stream = FakeStream();
      await pumpScreen(
        t,
        CoachPostMortemScreen(
          services: services(db, stream),
          lcId: c.lcId,
          summaryMd: 'Two pointers.',
        ),
        settle: false,
      );
      await t.pump(const Duration(milliseconds: 50));
      await answer(t, db, stream, data: c.cardsData);
      expectNoWords(t, 'coach post-mortem');
    });
  });

  group('focus', () {
    for (final active in [true, false]) {
      testWidgets('focus screen (project: $active)', (t) async {
        final db = FakeRtdb();
        final stream = FakeStream();
        final s = services(db, stream, kv: MemoryKv());
        addTearDown(s.focus.dispose);
        await pumpScreen(t, FocusScreen(services: s), settle: false);
        await answer(
          t,
          db,
          stream,
          data: {
            'day': '2026-11-02',
            'active': active ? {..._focusProject, 'minutes': 42} : null,
            'projects': [_focusProject],
            'gates': [
              {'id': 'leetcode', 'label': 'LeetCode', 'replaceable': true},
              {'id': 'workout', 'label': 'Workout', 'replaceable': false},
            ],
            'subjects': [
              {'id': 'automation', 'title': 'Automation'},
            ],
          },
        );
        expectNoWords(t, 'focus (project: $active)');
      });
    }
  });
}
