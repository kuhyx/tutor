// The comprehension check's own choices: chips like any question's, and a
// tapped one goes out marked `(picked option)` so the server can refuse to
// pass the check on a tap alone; an edited one goes out as typed.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/util/device.dart';

import '../support/composer.dart';
import '../support/ui.dart';

const _checkQ = 'Q4: What turns the piston push into rotation?';

void main() {
  tearDown(() => debugPhone = false);

  testWidgets('phone: a tapped check chip is sent with the marker', (t) async {
    final (db, stream) = await openComposer(t, phone: true, check: true);
    expect(find.text('1/4'), findsOneWidget);
    for (final a in ['one', 'two', 'three']) {
      await t.enterText(find.byType(TextField), a);
      await t.tap(find.text('Next'));
      await t.pumpAndSettle();
    }
    expect(find.text('4/4'), findsOneWidget);
    expect(find.textContaining('Comprehension check'), findsWidgets);
    expect(find.text('The flywheel'), findsOneWidget);
    await t.tap(find.text('The crankshaft'));
    await t.pump();
    expect(boxText(t), 'The crankshaft');
    await t.tap(find.text('Send'));
    await sent(t);
    final msg = await answer(t, db, stream, data: {'msg': 'm0006'});
    final body = msg['body'] as Map;
    expect(
      body['text'],
      allOf(
        contains('Q3: What closes the valves again after they open?\nA: three'),
        endsWith('$_checkQ\nA: The crankshaft $pickedMarker'),
      ),
    );
  });

  testWidgets('desktop: check chips show; an edited tap is not marked', (
    t,
  ) async {
    final (db, stream) = await openComposer(t, phone: false, check: true);
    expect(find.text('Hint'), findsNWidgets(4)); // the check's box too
    await t.ensureVisible(find.text('The flywheel'));
    await t.tap(find.text('The flywheel'));
    await t.pump();
    final check = find.byType(TextField).at(3);
    expect(t.widget<TextField>(check).controller!.text, 'The flywheel');
    await t.enterText(check, 'The flywheel, I think');
    await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await t.sendKeyEvent(LogicalKeyboardKey.enter);
    await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await sent(t);
    final msg = await answer(t, db, stream, data: {'msg': 'm0006'});
    final text = (msg['body'] as Map)['text'] as String;
    expect(text, endsWith('$_checkQ\nA: The flywheel, I think'));
    expect(text, isNot(contains(pickedMarker)));
  });
}
