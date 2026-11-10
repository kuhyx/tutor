import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/widgets/text_free_theme.dart';

import '../support/no_words.dart';

void main() {
  testWidgets('framework tooltips never show; an approved one does', (t) async {
    await t.pumpWidget(
      MaterialApp(
        theme: textFreeTheme(ThemeData()),
        home: Scaffold(
          body: Row(
            children: [
              IconButton(
                tooltip: 'Hidden words',
                onPressed: () {},
                icon: const Icon(Icons.add),
              ),
              approvedTooltip(message: 'Home', child: const Icon(Icons.home)),
            ],
          ),
        ),
      ),
    );
    await t.longPress(find.byIcon(Icons.add));
    await t.pumpAndSettle();
    expect(find.text('Hidden words'), findsNothing);
    await t.longPress(find.byIcon(Icons.home));
    await t.pumpAndSettle();
    expect(find.text('Home'), findsOneWidget);
    // Hidden ones are spoken only; the approved word is allowed.
    expect(wordsOnScreen(t), isEmpty);
  });

  testWidgets('a tooltip left painted fails the guard', (t) async {
    await t.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: IconButton(
            tooltip: 'Painted words',
            onPressed: () {},
            icon: const Icon(Icons.add),
          ),
        ),
      ),
    );
    expect(wordsOnScreen(t), ['tooltip: Painted words']);
  });
}
