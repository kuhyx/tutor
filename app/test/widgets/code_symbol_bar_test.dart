import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/widgets/code_symbol_bar.dart';

void main() {
  late TextEditingController c;
  setUp(() => c = TextEditingController());
  tearDown(() => c.dispose());

  Future<void> pump(WidgetTester t) => t.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Column(
          children: [
            TextField(controller: c, autofocus: true),
            CodeSymbolBar(controller: c),
          ],
        ),
      ),
    ),
  );

  testWidgets('has the symbols the phone keyboard buries', (t) async {
    await pump(t);
    for (final s in ['(', ')', ',', "'", '"', '=', '<', '>', '*', '_', ';']) {
      expect(codeSymbolKeys, contains(s));
    }
    for (final s in ['[', ']', ':', '  ']) {
      expect(codeSymbolKeys, contains(s));
    }
    expect(find.text('⇥'), findsOneWidget);
  });

  testWidgets('a key types at the cursor and keeps the keyboard up', (t) async {
    await pump(t);
    await t.enterText(find.byType(TextField), 'f(x');
    c.selection = const TextSelection.collapsed(offset: 1);
    await t.pump();
    await t.tap(find.byKey(const ValueKey('key-[')));
    await t.pump();
    expect(c.text, 'f[(x');
    expect(c.selection.baseOffset, 2);
    expect(
      t.widget<EditableText>(find.byType(EditableText)).focusNode.hasFocus,
      isTrue,
    );
  });

  testWidgets('a key replaces the selection; tab is two spaces', (t) async {
    await pump(t);
    await t.enterText(find.byType(TextField), 'abc');
    c.selection = const TextSelection(baseOffset: 0, extentOffset: 2);
    await t.pump();
    for (final k in ['key-:', 'key-  ']) {
      await t.ensureVisible(find.byKey(ValueKey(k)));
      await t.tap(find.byKey(ValueKey(k)));
    }
    await t.pump();
    expect(c.text, ':  c');
  });

  testWidgets('with no selection a key appends', (t) async {
    await pump(t);
    c.value = const TextEditingValue(text: 'ab');
    await t.pump();
    await t.tap(find.byKey(const ValueKey('key-;')));
    expect(c.text, 'ab;');
  });
}
