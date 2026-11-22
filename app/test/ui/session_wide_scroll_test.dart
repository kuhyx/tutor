// The wide desktop chat (kuhy, 2026-11-22): the latest tutor reply starts
// right under the top bar, its questions and Send follow in the same
// scroll (nothing pinned), older turns sit one wheel-scroll up, and a new
// turn lands with its top under the bar again.
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/util/device.dart';

import '../support/composer.dart';
import '../support/label_finders.dart';

const _screen = Size(1920, 1080);

Finder _scrollOf(Finder f) =>
    find.ancestor(of: f, matching: find.byType(Scrollable)).first;

Future<void> _wheel(WidgetTester t, Offset at, double dy) async {
  final pointer = TestPointer(1, PointerDeviceKind.mouse);
  await t.sendEventToBinding(pointer.hover(at));
  await t.sendEventToBinding(pointer.scroll(Offset(0, dy)));
  await t.pumpAndSettle();
}

void main() {
  tearDown(() => debugPhone = false);

  testWidgets('the reply under the bar, Q1-Q3 and Send below, one scroll', (
    t,
  ) async {
    await openComposer(t, phone: false, size: _screen);
    final bar = t.getRect(find.byType(AppBar));
    final reply = rich('Good. Now three quick ones');
    expect(t.getRect(reply).top - bar.bottom, lessThan(48), reason: 'no gap');
    final send = controlByLabel('Send');
    expect(t.getRect(send).bottom, lessThanOrEqualTo(_screen.height));
    expect(
      t.getRect(find.byType(TextField).at(2)).bottom,
      lessThanOrEqualTo(_screen.height),
    );
    // Nothing pinned: the boxes scroll with the reply.
    expect(t.widget(_scrollOf(send)), same(t.widget(_scrollOf(reply))));
  });

  testWidgets('wheel up over the margin shows older turns', (t) async {
    await openComposer(t, phone: false, size: _screen);
    final older = rich('Right. The piston goes down');
    final reply = rich('Good. Now three quick ones');
    final before = t.getRect(reply).top;
    // The margin left of the 960 px column.
    await _wheel(t, const Offset(100, 500), -600);
    expect(t.getRect(reply).top, greaterThan(before + 300));
    expect(older.hitTestable(), findsWidgets);
    await _wheel(t, const Offset(100, 500), 2000);
    expect(t.getRect(reply).top, closeTo(before, 1));
  });

  testWidgets('a typed answer and its focus survive scrolling away', (t) async {
    await openComposer(t, phone: false, size: _screen);
    final q2 = find.byType(TextField).at(1);
    await t.tap(q2);
    await t.enterText(q2, 'two per turn');
    await t.pump();
    await _wheel(t, const Offset(100, 500), -5000);
    await _wheel(t, const Offset(100, 500), 5000);
    final box = t.widget<TextField>(find.byType(TextField).at(1));
    expect(box.controller!.text, 'two per turn');
    expect(box.focusNode?.hasFocus ?? true, isTrue);
    final editable = t.widget<EditableText>(
      find.descendant(
        of: find.byType(TextField).at(1),
        matching: find.byType(EditableText),
      ),
    );
    expect(editable.focusNode.hasFocus, isTrue);
  });

  testWidgets('a new turn lands with its top under the bar', (t) async {
    final (db, stream) = await openComposer(t, phone: false, size: _screen);
    await _wheel(t, const Offset(100, 500), -600);
    db.root = setAt(db.root, '$composeBase/msgs/m0099', {
      'role': 'tutor',
      'text': 'A brand new reply.',
      'questions': ['One more?'],
      'at': 1,
    });
    stream.emit(
      '$composeBase/msgs',
      RtdbPut('/', getAt(db.root, '$composeBase/msgs')),
    );
    await t.pumpAndSettle();
    final bar = t.getRect(find.byType(AppBar));
    final reply = t.getRect(rich('A brand new reply.'));
    expect(reply.top - bar.bottom, lessThan(48));
    expect(reply.top, greaterThanOrEqualTo(bar.bottom));
  });
}
