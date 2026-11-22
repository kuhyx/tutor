// The hint bulb sits inside the answer box, right beside the pencil (kuhy,
// 2026-11-22): no row under the question holds only a bulb, and the bulb
// keeps its own "Hint" button in the semantics tree (not merged into the
// textbox).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/util/device.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/composer.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

Iterable<Rect> _rects(WidgetTester t, Finder f) => [
  for (var i = 0; i < f.evaluate().length; i++) t.getRect(f.at(i)),
];

Rect _inside(WidgetTester t, Finder glyph) {
  final r = t.getRect(glyph);
  final boxes = _rects(t, find.byType(TextField));
  return boxes.firstWhere(
    (b) => b.contains(r.center),
    orElse: () => fail('bulb at $r is in no answer box'),
  );
}

void main() {
  tearDown(() => debugPhone = false);

  testWidgets('desktop: a bulb in each box, beside the pencil', (t) async {
    final semantics = t.ensureSemantics();
    final (db, stream) = await openComposer(
      t,
      phone: false,
      size: const Size(1920, 1080),
      edit: (m) => m.remove('choices'), // no choices: no chip row at all
    );
    final bulbs = glyphsLabelled('Hint');
    expect(bulbs, findsNWidgets(3));
    for (var i = 0; i < 3; i++) {
      final bulb = t.getRect(bulbs.at(i));
      final box = _inside(t, bulbs.at(i));
      final pencils = _rects(t, find.byIcon(Icons.edit_outlined));
      final pencil = pencils.firstWhere((p) => box.contains(p.center));
      expect(bulb.left, greaterThanOrEqualTo(pencil.right - 1));
      expect(bulb.left - pencil.right, lessThan(16), reason: 'right beside');
      final icon = t.getRect(
        find.descendant(of: bulbs.at(i), matching: find.byType(Icon)),
      );
      expect(icon.width, 16);
    }
    expect(find.byType(ActionChip), findsNothing);
    expect(find.bySemanticsLabel(RegExp(r'^Hint$')), findsNWidgets(3));
    expect(find.bySemanticsLabel(RegExp('^Your answer')), findsNWidgets(3));

    await t.tap(bulbs.at(1));
    await sent(t);
    final msg = await answer(t, db, stream, data: {'msg': 'm0006'});
    expect(msg['body'], {
      'session': fixtureLiveSid,
      'text': 'Hint',
      'device': 'desktop',
    });
    semantics.dispose();
  });

  testWidgets('phone: the bulb sits in the open field', (t) async {
    await openComposer(t, phone: true, edit: (m) => m.remove('choices'));
    final bulb = glyphsLabelled('Hint');
    expect(bulb, findsOneWidget);
    final box = _inside(t, bulb);
    // The bulb does not grow the one-line field (44 dp without it).
    expect(box.height, lessThanOrEqualTo(44), reason: '$box');
  });

  testWidgets('phone: a closed field keeps the bulb in the row', (t) async {
    await openComposer(t, phone: true);
    expect(find.byType(TextField), findsNothing);
    expect(glyphsLabelled('Hint'), findsOneWidget);
    await openField(t);
    final bulb = glyphsLabelled('Hint');
    expect(bulb, findsOneWidget);
    _inside(t, bulb);
  });
}
