// The wide desktop chat (kuhy, 2026-11-22): the latest tutor reply starts
// right under the top bar, older turns sit one wheel-scroll up, and a new
// turn lands with its top under the bar again. The answer panel (Q1-Q3,
// their boxes, Send) is pinned at the bottom in one constant place and
// fits whole: it never scrolls (b3140572-1).
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

  testWidgets('the reply under the bar, Q1-Q3 and Send pinned below', (
    t,
  ) async {
    await openComposer(t, phone: false, size: _screen);
    final bar = t.getRect(find.byType(AppBar));
    final reply = rich('Good. Now three quick ones');
    expect(t.getRect(reply).top - bar.bottom, lessThan(48), reason: 'no gap');
    final send = controlByLabel('Send');
    expect(t.getRect(send).bottom, greaterThan(_screen.height - 48));
    expect(t.getRect(send).bottom, lessThanOrEqualTo(_screen.height));
    expect(
      t.getRect(find.byType(TextField).at(0)).top,
      greaterThan(bar.bottom),
    );
    // Pinned: the boxes are not in the chat's scroll ...
    expect(t.widget(_scrollOf(send)), isNot(same(t.widget(_scrollOf(reply)))));
    // ... and the panel fits whole: nothing in it scrolls.
    final panel = t.state<ScrollableState>(_scrollOf(send)).position;
    expect(panel.maxScrollExtent, 0);
    // The whole latest turn shows above the panel: nothing of it is
    // hidden below (its scroll has no room past offset 0).
    final chat = t.state<ScrollableState>(_scrollOf(reply)).position;
    expect(chat.maxScrollExtent, 0);
    expect(
      t.getRect(reply).bottom,
      lessThanOrEqualTo(t.getRect(find.byType(TextField).at(0)).top),
    );
  });

  testWidgets('Send stays put while the chat scrolls and turns arrive', (
    t,
  ) async {
    final (db, stream) = await openComposer(t, phone: false, size: _screen);
    final send = controlByLabel('Send');
    final at = t.getRect(send);
    await _wheel(t, const Offset(100, 300), -600);
    expect(t.getRect(send), at);
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
    expect(t.getRect(send), at);
  });

  testWidgets('wheel up over the margin shows older turns', (t) async {
    await openComposer(t, phone: false, size: _screen);
    final older = rich('Right. The piston goes down');
    final reply = rich('Good. Now three quick ones');
    final before = t.getRect(reply).top;
    // The margin left of the 960 px column.
    // The chat above the pinned panel is about 490 px tall.
    await _wheel(t, const Offset(100, 300), -300);
    expect(t.getRect(reply).top, greaterThan(before + 250));
    // At the top of the scroll the older turn shows under the bar.
    await _wheel(t, const Offset(100, 300), -5000);
    final bar = t.getRect(find.byType(AppBar)).bottom;
    expect(t.getRect(older.last).top, greaterThanOrEqualTo(bar));
    expect(t.getRect(older.last).top, lessThan(bar + 480));
    await _wheel(t, const Offset(100, 300), 9000);
    expect(t.getRect(reply).top, closeTo(before, 1));
  });

  testWidgets('a typed answer and its focus survive scrolling away', (t) async {
    await openComposer(t, phone: false, size: _screen);
    final q2 = find.byType(TextField).at(1);
    await t.tap(q2);
    await t.enterText(q2, 'two per turn');
    await t.pump();
    await _wheel(t, const Offset(100, 300), -5000);
    await _wheel(t, const Offset(100, 300), 5000);
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

  // Flutter web's accessibility mode types into the field's semantics node:
  // a node culled while scrolled away came back empty (live check C17).
  testWidgets('a typed answer keeps its semantics node while scrolled away', (
    t,
  ) async {
    final handle = t.ensureSemantics();
    await openComposer(t, phone: false, size: _screen);
    final q2 = find.byType(TextField).at(1);
    await t.tap(q2);
    await t.enterText(q2, 'two per turn');
    await t.pump();
    expect(find.semantics.byValue('two per turn'), findsOne);
    await _wheel(t, const Offset(100, 300), -1500);
    expect(t.getRect(q2).bottom, lessThan(_screen.height), reason: 'pinned');
    expect(find.semantics.byValue('two per turn'), findsOne);
    handle.dispose();
  });

  testWidgets('a new turn lands with its top under the bar', (t) async {
    final (db, stream) = await openComposer(t, phone: false, size: _screen);
    await _wheel(t, const Offset(100, 300), -600);
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
