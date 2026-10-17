// All tutor-side text selects and copies as one selection: the chat list
// (messages, the "Tutor" tag, questions) sits in ONE SelectionArea and its
// markdown is plain Text.rich (a nested SelectableText would split the
// selection per block); the composer's question labels are selectable too,
// while its boxes and chips keep working.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/util/device.dart';

import '../support/composer.dart';

Finder _area(Finder of) =>
    find.ancestor(of: of, matching: find.byType(SelectionArea));

void main() {
  tearDown(() => debugPhone = false);

  testWidgets('chat text shares one SelectionArea; no SelectableText', (
    t,
  ) async {
    await openComposer(t, phone: false);
    final message = rich('Good. Now three quick ones');
    expect(_area(message), findsOneWidget);
    expect(_area(find.text('Tutor').first), findsOneWidget);
    final area = t.widget(_area(message));
    // An older message's question, further up the chat: the same area.
    final question = find.text('What moves inside the cylinder?');
    await t.dragUntilVisible(
      question,
      find.byType(ListView).first,
      const Offset(0, 300),
    );
    expect(t.widget(_area(question)), same(area));
    expect(find.byType(SelectableText), findsNothing);
  });

  testWidgets('composer labels selectable; boxes and chips still work', (
    t,
  ) async {
    await openComposer(t, phone: false);
    expect(_area(find.text('Q1: Which stroke makes the power?')), findsWidgets);
    final box = find.byType(TextField).first;
    await t.tap(box);
    await t.pump();
    final editable = find.descendant(
      of: box,
      matching: find.byType(EditableText),
    );
    expect(t.widget<EditableText>(editable).focusNode.hasFocus, isTrue);
    await t.enterText(box, 'typed');
    expect(t.widget<TextField>(box).controller!.text, 'typed');
    await t.ensureVisible(find.text('The camshaft lobe'));
    await t.tap(find.text('The camshaft lobe'));
    await t.pump();
    final third = find.byType(TextField).at(2);
    expect(t.widget<TextField>(third).controller!.text, 'The camshaft lobe');
  });
}
