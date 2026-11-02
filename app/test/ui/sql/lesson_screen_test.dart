import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/ui/sql/lesson_parts.dart';
import 'package:tutor/ui/sql/lesson_screen.dart';

import '../../sql/sql_fixtures.dart';
import '../../support/fake_rtdb.dart';
import '../../support/fake_stream.dart';
import '../../support/services.dart';
import '../../support/ui.dart';

const _next = <String, Object?>{
  'lesson_id': 'a1b2c3d4e5f6',
  'progress': {'concept': 'NULL comparisons', 'index': 0, 'total': 2},
  'question_md': 'Now the NOT variant: what changes?',
  'feedback_md': 'Good, and why?',
};

void main() {
  late FakeRtdb db;
  late FakeStream stream;
  late MemoryKv kv;

  Future<void> open(
    WidgetTester t, {
    String topic = 'basics',
    Map<String, Object?>? first = lessonTurnData,
    double? keyboard,
  }) async {
    db = FakeRtdb();
    stream = FakeStream();
    await pumpScreen(
      t,
      SqlLessonScreen(
        services: services(db, stream, kv: kv),
        topic: topic,
      ),
      settle: false,
    );
    if (keyboard != null) {
      t.view
        ..physicalSize = const Size(1080, 2400)
        ..devicePixelRatio = 2.625
        ..padding = const FakeViewPadding(top: 132, bottom: 63)
        ..viewInsets = FakeViewPadding(bottom: keyboard);
    }
    await t.pump(const Duration(milliseconds: 50));
    if (first != null) await answer(t, db, stream, data: first);
  }

  setUp(() => kv = MemoryKv());

  Map<String, dynamic> body() =>
      lastRequest(db).$2['body'] as Map<String, dynamic>;

  testWidgets('starts a lesson and shows tables, feedback, question', (
    t,
  ) async {
    await open(t);
    expect(lastRequest(db).$2['kind'], 'sql_lesson_turn');
    expect(body(), {'topic': 'basics'});
    expect(find.text('customers'), findsWidgets);
    expect(find.text('Ann'), findsWidgets);
    expect(find.text('Not quite.'), findsOneWidget);
    expect(find.text('UNKNOWN'), findsOneWidget); // the summary table
    expect(find.textContaining('Which names'), findsOneWidget);
    expect(find.text('NULL comparisons'), findsOneWidget);
    expect(find.text('1/2'), findsOneWidget);
    expect(kv.data['sql.lesson.basics'], 'a1b2c3d4e5f6');
  });

  testWidgets('an answer goes out with the lesson id; tables stay', (t) async {
    await open(t);
    await t.enterText(find.byKey(const ValueKey('answer')), 'Ann, since 2<>2');
    await t.pump();
    await t.tap(find.byKey(const ValueKey('send')));
    await t.pump(const Duration(milliseconds: 50));
    expect(body(), {
      'topic': 'basics',
      'lesson_id': 'a1b2c3d4e5f6',
      'answer': 'Ann, since 2<>2',
    });
    expect(find.text('Ann, since 2<>2'), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    await answer(t, db, stream, data: _next);
    expect(find.textContaining('Now the NOT variant'), findsOneWidget);
    expect(find.text('customers'), findsWidgets);
    expect(find.text('Ann'), findsWidgets);
    final box = t.widget<TextField>(find.byKey(const ValueKey('answer')));
    expect(box.controller!.text, isEmpty);
  });

  testWidgets('a saved lesson resumes; an unknown one starts over', (t) async {
    kv.data['sql.lesson.basics'] = 'old';
    await open(t, first: null);
    expect(body(), {'topic': 'basics', 'lesson_id': 'old'});
    await answer(
      t,
      db,
      stream,
      code: 'bad_request',
      error: 'unknown',
      settle: false,
    );
    expect(body(), {'topic': 'basics'});
    expect(kv.data.containsKey('sql.lesson.basics'), isFalse);
    await answer(t, db, stream, data: lessonTurnData);
    expect(find.textContaining('Which names'), findsOneWidget);
  });

  testWidgets('a bad turn is reported, not thrown', (t) async {
    await open(t, first: const {'lesson_id': 5});
    expect(find.textContaining('lesson_id'), findsOneWidget);
  });

  testWidgets('done offers the next topic', (t) async {
    await open(
      t,
      first: const {'lesson_id': 'z', 'done': true, 'summary_md': 'All set.'},
    );
    expect(find.text('All set.'), findsOneWidget);
    expect(find.byKey(const ValueKey('answer')), findsNothing);
    await t.tap(find.byKey(const ValueKey('next-topic')));
    await t.pump();
    await t.pump(const Duration(milliseconds: 400));
    expect(body(), {'topic': 'joins-null'});
  });

  testWidgets('the last topic ends with a check, no next', (t) async {
    await open(
      t,
      topic: 'strings',
      first: const {'lesson_id': 'z', 'done': true},
    );
    expect(find.byKey(const ValueKey('next-topic')), findsNothing);
    expect(find.byIcon(Icons.check_circle_outline), findsOneWidget);
  });

  testWidgets('wide: the tables pane stays while the thread scrolls', (
    t,
  ) async {
    await open(t);
    expect(find.byKey(const ValueKey('tables-pane')), findsOneWidget);
    expect(find.byKey(const ValueKey('tables-header')), findsNothing);
    for (var i = 0; i < 12; i++) {
      await t.enterText(find.byKey(const ValueKey('answer')), 'a$i');
      await t.pump();
      await t.tap(find.byKey(const ValueKey('send')));
      await t.pump(const Duration(milliseconds: 50));
      await answer(t, db, stream, data: _next);
    }
    expect(find.text('Ann'), findsWidgets);
    final pane = t.getRect(find.byKey(const ValueKey('tables-pane')));
    expect(t.getRect(find.text('Ann').first).top, greaterThan(pane.top));
  });

  group('phone', () {
    testWidgets('the tables header folds the tables', (t) async {
      await open(t, keyboard: 0);
      final inTables = find.descendant(
        of: find.byType(PinnedTables),
        matching: find.text('Ann'),
      );
      expect(inTables, findsOneWidget);
      await t.tap(find.byKey(const ValueKey('tables-header')));
      await t.pump();
      expect(inTables, findsNothing);
      await t.tap(find.byKey(const ValueKey('tables-header')));
      await t.pump();
      expect(inTables, findsOneWidget);
    });

    testWidgets('with the keyboard up, header and answer box stay in view', (
      t,
    ) async {
      await open(t, keyboard: 800);
      await t.tap(find.byKey(const ValueKey('answer')));
      await t.pump(const Duration(milliseconds: 100));
      const dpr = 2.625;
      const top = 132 / dpr;
      const keyboardTop = (2400 - 800) / dpr;
      final header = t.getRect(find.byKey(const ValueKey('tables-header')));
      final box = t.getRect(find.byKey(const ValueKey('answer')));
      expect(header.top, greaterThanOrEqualTo(top));
      expect(box.bottom, lessThanOrEqualTo(keyboardTop));
      expect(box.top, greaterThan(header.bottom));
      expect(
        find.descendant(
          of: find.byType(PinnedTables),
          matching: find.text('Ann'),
        ),
        findsNothing,
      );
    });

    testWidgets('the unfolded tables never fill the screen', (t) async {
      await open(t, keyboard: 800);
      final box = t.getRect(find.byKey(const ValueKey('answer')));
      final thread = t.getSize(find.byType(ListView).last);
      expect(box.bottom, lessThanOrEqualTo((2400 - 800) / 2.625));
      expect(thread.height, greaterThan(100));
    });
  });
}
