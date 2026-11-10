import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/widgets/icon_field.dart';

import '../support/label_finders.dart';
import '../support/no_words.dart';

void main() {
  testWidgets('a field has a leading glyph, no hint, a spoken label', (
    t,
  ) async {
    await t.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: FieldLabel(
            semanticLabel: 'Name',
            child: TextField(
              decoration: iconDecoration(
                Icons.person,
                suffixIcon: const Icon(Icons.clear),
                dense: true,
                border: InputBorder.none,
              ),
            ),
          ),
        ),
      ),
    );
    final d = t.widget<InputDecorator>(find.byType(InputDecorator)).decoration;
    expect(d.hintText, isNull);
    expect(d.labelText, isNull);
    expect(find.byIcon(Icons.person), findsOneWidget);
    expect(fieldByLabel('Name'), findsOneWidget);
    await t.enterText(find.byType(TextField), 'typed words stay');
    expectNoWords(t, 'field'); // a typed value is content
    final h = t.ensureSemantics();
    expect(find.bySemanticsLabel('Name'), findsOneWidget);
    h.dispose();
  });
}
