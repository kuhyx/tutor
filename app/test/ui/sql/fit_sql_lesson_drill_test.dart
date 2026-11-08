// build-mobile-app R7: an SQL lesson and drill fit one Pixel 6a screen;
// with the keyboard up the input typed in and Run (or Send) stay visible.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/ui/sql/drill_screen.dart';
import 'package:tutor/ui/sql/lesson_screen.dart';

import '../../sql/sql_fixtures.dart';
import '../../support/fake_rtdb.dart';
import '../../support/fake_stream.dart';
import '../../support/fit.dart';
import '../../support/services.dart';
import '../../support/ui.dart';

Finder _key(String k) => find.byKey(ValueKey(k));

Future<void> _keyboard(WidgetTester t, double scale, Finder field) async {
  await t.tap(field.hitTestable().first);
  pixelView(t, scale: scale, keyboard: fitKeyboard);
  await t.pumpAndSettle();
}

void main() {
  fitTest('SQL lesson', (t, scale) async {
    pixelView(t, scale: scale);
    final db = FakeRtdb();
    final stream = FakeStream();
    await pumpFit(
      t,
      SqlLessonScreen(
        services: services(db, stream, kv: MemoryKv()),
        topic: 'basics',
      ),
      settle: false,
    );
    await answer(t, db, stream, data: lessonTurnData);
    for (var i = 0; i < 3; i++) {
      await t.enterText(_key('answer'), 'answer $i');
      await t.pump();
      await t.tap(_key('send'));
      await sent(t);
      await answer(t, db, stream, data: lessonTurnData);
    }
    await t.pumpAndSettle();
    expectFits(t, state: 'lesson');
    await _keyboard(t, scale, _key('answer'));
    expectFits(t, state: 'lesson + keyboard');
    expectReachable(t, _key('send'), state: 'keyboard');
  });

  for (final predict in [false, true]) {
    fitTest('SQL drill, predict: $predict', (t, scale) async {
      pixelView(t, scale: scale);
      final db = FakeRtdb();
      final stream = FakeStream();
      await pumpFit(
        t,
        SqlDrillScreen(
          services: services(db, stream, kv: MemoryKv()),
          id: 'basics-1',
          title: 'Count rows',
        ),
        settle: false,
      );
      await answer(
        t,
        db,
        stream,
        data: predict ? predictDrillData : writeDrillData,
      );
      await t.pumpAndSettle();
      expectFits(t, state: 'task');
      await t.tap(find.byIcon(Icons.edit_note));
      await t.pumpAndSettle();
      expectFits(t, state: 'answer');
      final action = _key(predict ? 'check' : 'run');
      expectReachable(t, action);
      final field = predict ? _key('cell-0-0') : _key('sql-editor');
      await _keyboard(t, scale, field);
      expectFits(t, state: 'answer + keyboard');
      expectReachable(t, action, state: 'keyboard');
      if (!predict) {
        await t.enterText(_key('sql-editor'), 'SELECT 1');
        await t.pump();
      }
      await t.tap(action);
      await sent(t);
      await answer(t, db, stream, data: runBadData);
      await t.pumpAndSettle();
      expectFits(t, state: 'result + keyboard');
      expectReachable(t, action, state: 'result');
    });
  }
}
