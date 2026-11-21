// textgate guard, SQL practice: the drill list, write and predict drills and
// a lesson turn paint no app words (the other practice screens:
// no_words_practice_test.dart).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/ui/sql/drill_screen.dart';
import 'package:tutor/ui/sql/lesson_screen.dart';
import 'package:tutor/ui/sql/sql_screen.dart';

import '../sql/sql_fixtures.dart' as q;
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/no_words.dart';
import '../support/services.dart';
import '../support/ui.dart';

void main() {
  group('sql', () {
    late FakeRtdb db;
    late FakeStream stream;
    late MemoryKv kv;
    setUp(() => kv = MemoryKv());

    Future<void> drill(WidgetTester t, Map<String, Object?> data) async {
      db = FakeRtdb();
      stream = FakeStream();
      await pumpScreen(
        t,
        SqlDrillScreen(
          services: services(db, stream, kv: kv),
          id: 'basics-1',
          title: 'Count rows',
        ),
        settle: false,
      );
      await answer(t, db, stream, data: data);
    }

    Future<void> run(WidgetTester t, String sql) async {
      await t.enterText(find.byKey(const ValueKey('sql-editor')), sql);
      await t.pump();
      await t.tap(find.byKey(const ValueKey('run')));
      await t.pump(const Duration(milliseconds: 50));
    }

    testWidgets('list of drills', (t) async {
      db = FakeRtdb();
      stream = FakeStream();
      await pumpScreen(
        t,
        SqlPracticeScreen(services: services(db, stream)),
        settle: false,
      );
      await answer(t, db, stream, data: q.listData);
      expectNoWords(t, 'sql list');
    });

    testWidgets('write drill: wrong result, hint, error', (t) async {
      await drill(t, q.writeDrillData);
      expectNoWords(t, 'sql drill');
      await run(t, 'select count(*) from emp');
      await answer(t, db, stream, data: q.runBadData);
      expectNoWords(t, 'sql drill wrong result');
      await t.tap(find.byKey(const ValueKey('hint')));
      await t.pump(const Duration(milliseconds: 50));
      await answer(t, db, stream, data: const {'question': 'Which rows?'});
      expectNoWords(t, 'sql drill hint');
      await run(t, 'selec');
      await answer(t, db, stream, data: const {'ok': false, 'error': 'E 1064'});
      expectNoWords(t, 'sql drill error');
    });

    testWidgets('a malformed result is an error cue', (t) async {
      await drill(t, q.writeDrillData);
      await run(t, 'select 1');
      await answer(t, db, stream, data: const {'rows': 5});
      expectNoWords(t, 'sql drill malformed');
    });

    testWidgets('predict drill', (t) async {
      await drill(t, q.predictDrillData);
      expectNoWords(t, 'sql predict');
    });

    testWidgets('lesson turn', (t) async {
      db = FakeRtdb();
      stream = FakeStream();
      await pumpScreen(
        t,
        SqlLessonScreen(
          services: services(db, stream, kv: kv),
          topic: 'basics',
        ),
        settle: false,
      );
      await t.pump(const Duration(milliseconds: 50));
      await answer(t, db, stream, data: q.lessonTurnData);
      expectNoWords(t, 'sql lesson');
    });
  });
}
