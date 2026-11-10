import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/widgets/content_text.dart';

import '../support/no_words.dart';

Future<void> _pump(WidgetTester t, Widget child) =>
    t.pumpWidget(MaterialApp(home: Scaffold(body: child)));

void main() {
  testWidgets('shows plain and rich content, which the guard allows', (
    t,
  ) async {
    await _pump(
      t,
      const Column(
        children: [
          ContentText('The four-stroke engine', maxLines: 1),
          ContentText.rich(
            TextSpan(
              children: [
                TextSpan(text: 'rich '),
                TextSpan(text: 'content'),
              ],
            ),
          ),
          ContentScope(child: Text('markdown body words')),
        ],
      ),
    );
    expect(find.text('The four-stroke engine'), findsOneWidget);
    expect(find.textContaining('rich content'), findsOneWidget);
    expect(find.text('markdown body words'), findsOneWidget);
    expectNoWords(t, 'content');
  });

  testWidgets('the same words outside content fail the guard', (t) async {
    await _pump(t, const Text('Some words'));
    expect(wordsOnScreen(t), ['text: Some words']);
  });

  testWidgets('digits, one letter and approved words pass', (t) async {
    await _pump(
      t,
      const Column(children: [Text('12/30'), Text('G'), Text('Start')]),
    );
    expect(wordsOnScreen(t), isEmpty);
  });

  testWidgets('a field decoration with words fails, an icon one passes', (
    t,
  ) async {
    await _pump(
      t,
      const TextField(decoration: InputDecoration(hintText: 'e.g. a thing')),
    );
    expect(wordsOnScreen(t), contains('field: e.g. a thing'));
  });
}
