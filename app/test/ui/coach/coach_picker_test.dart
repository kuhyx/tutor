import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/coach/coach_picker.dart';
import 'package:tutor/ui/coach/coach_screen.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../../coach/coach_fixtures.dart';
import '../../support/fake_rtdb.dart';
import '../../support/fake_stream.dart';
import '../../support/label_finders.dart';
import '../../support/services.dart';
import '../../support/ui.dart';

void main() {
  late FakeRtdb db;
  late FakeStream stream;

  Future<void> open(WidgetTester t, {Size? size}) async {
    db = FakeRtdb();
    stream = FakeStream();
    await pumpScreen(
      t,
      CoachPickerScreen(services: services(db, stream)),
      settle: false,
      size: size ?? const Size(1366, 900),
    );
    expect(lastRequest(db).$2['kind'], 'lc_list');
    await answer(t, db, stream, data: listData);
  }

  Map<String, dynamic> body() =>
      lastRequest(db).$2['body'] as Map<String, dynamic>;

  Future<void> opened(WidgetTester t) async {
    await t.pump();
    await t.pump(const Duration(milliseconds: 400));
    expect(find.byType(CoachScreen), findsOneWidget);
    expect(lastRequest(db).$2['kind'], 'lc_open');
  }

  testWidgets('lists due re-tests with the no-submit notice, and recent', (
    t,
  ) async {
    await open(t);
    expect(find.text('Group Anagrams'), findsOneWidget);
    expect(
      find.text('Re-test: do NOT submit this on LeetCode'),
      findsOneWidget,
    );
    expect(find.text('Two Sum'), findsOneWidget);
    expect(find.text('lru-cache'), findsOneWidget);
    expect(find.text('hashing'), findsOneWidget);
  });

  testWidgets('no due re-tests: no notice', (t) async {
    db = FakeRtdb();
    stream = FakeStream();
    await pumpScreen(
      t,
      CoachPickerScreen(services: services(db, stream)),
      settle: false,
    );
    await answer(t, db, stream);
    expect(find.text('Re-test: do NOT submit this on LeetCode'), findsNothing);
  });

  testWidgets('a pasted URL opens that problem by its slug', (t) async {
    await open(t);
    await t.enterText(
      find.byKey(const ValueKey('problem')),
      'https://leetcode.com/problems/two-sum/description/',
    );
    await t.tap(find.byKey(const ValueKey('go')));
    await opened(t);
    expect(body(), {'problem': 'two-sum'});
  });

  testWidgets('the keyboard action starts too; junk starts nothing', (t) async {
    await open(t);
    await t.enterText(find.byKey(const ValueKey('problem')), 'not a slug!');
    await t.tap(find.byKey(const ValueKey('go')));
    await t.pump();
    expect(find.byType(CoachScreen), findsNothing);
    expect(lastRequest(db).$2['kind'], 'lc_list');
    await t.enterText(find.byKey(const ValueKey('problem')), 'lru-cache');
    await t.testTextInput.receiveAction(TextInputAction.go);
    await opened(t);
    expect(body(), {'problem': 'lru-cache'});
  });

  testWidgets('a recent session resumes by its id', (t) async {
    await open(t);
    await t.tap(find.text('Two Sum'));
    await opened(t);
    expect(body(), {'lc_id': lcId});
  });

  testWidgets('a due re-test opens its problem', (t) async {
    await open(t);
    await t.tap(find.text('Group Anagrams'));
    await opened(t);
    expect(body(), {'problem': 'group-anagrams'});
  });

  testWidgets('a cluster lists its problems', (t) async {
    await open(t);
    await t.tap(find.text('hashing'));
    await t.pumpAndSettle();
    await t.tap(find.text('valid-anagram'));
    await opened(t);
    expect(body(), {'problem': 'valid-anagram'});
  });

  testWidgets('a failed list shows the error', (t) async {
    db = FakeRtdb();
    stream = FakeStream();
    await pumpScreen(
      t,
      CoachPickerScreen(services: services(db, stream)),
      settle: false,
    );
    await answer(
      t,
      db,
      stream,
      code: 'worker_error',
      error: 'down',
      extra: {'retry': true},
    );
    expect(controlByLabel('Retry'), findsOneWidget);
  });

  testWidgets('a damaged list shows the problem', (t) async {
    db = FakeRtdb();
    stream = FakeStream();
    await pumpScreen(
      t,
      CoachPickerScreen(services: services(db, stream)),
      settle: false,
    );
    await answer(t, db, stream, data: {'recent': 3});
    expect(cueOfKind(CueKind.error), findsOneWidget);
  });
}
