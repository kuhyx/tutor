import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/widgets/spoken_label.dart';
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

  Widget glyphApp(Widget body) => MaterialApp(
    theme: textFreeTheme(ThemeData()),
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(body: Center(child: body)),
  );

  testWidgets('a glyph tooltip shows its one ledger word, spoken once', (
    t,
  ) async {
    final handle = t.ensureSemantics();
    await t.pumpWidget(
      glyphApp(
        GlyphButton(
          icon: Icons.sync,
          semanticLabel: 'Sync now',
          tooltip: (l) => l.tooltip_sync,
          onPressed: () {},
        ),
      ),
    );
    expect(find.bySemanticsLabel('Sync now'), findsOneWidget);
    // The word is painted on demand, never spoken: the label says it.
    expect(find.bySemanticsLabel(RegExp(r'^Sync$')), findsNothing);
    await t.longPress(find.byIcon(Icons.sync));
    await t.pumpAndSettle();
    expect(find.text('Sync'), findsOneWidget);
    expect(wordsOnScreen(t), isEmpty);
    handle.dispose();
  });

  testWidgets('a glyph without a tooltip shows none', (t) async {
    await t.pumpWidget(
      glyphApp(
        GlyphButton(
          icon: Icons.sync,
          semanticLabel: 'Sync now',
          onPressed: () {},
        ),
      ),
    );
    expect(find.byType(Tooltip), findsNothing);
  });

  testWidgets('a shown tooltip of two words still fails the guard', (t) async {
    await t.pumpWidget(
      glyphApp(approvedTooltip(message: 'Two words', child: const Text('1'))),
    );
    expect(wordsOnScreen(t), ['tooltip: Two words']);
  });
}
