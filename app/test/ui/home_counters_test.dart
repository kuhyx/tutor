// Home's Today counters: own minutes and LeetCode minutes as two more glyph
// stats beside the bank, each only when > 0 (part e79be0be-1, mockup F8).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/ui/home_counters.dart';
import 'package:tutor/widgets/count_badge.dart';

import '../support/label_finders.dart';

Today _today(Map<String, Object?> extra) => Today.fromJson({
  'day': '2026-11-27',
  'credited_minutes': 15,
  'target': 15,
  'new': 0,
  'active_minutes': 0,
  ...extra,
});

Future<void> _pump(WidgetTester t, Today today) => t.pumpWidget(
  MaterialApp(
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(body: HomeCounters(today)),
  ),
);

Finder _stat(IconData icon, String value) => find.byWidgetPredicate(
  (w) => w is GlyphStat && w.icon == icon && w.value == value,
);

void main() {
  testWidgets('own and LeetCode minutes show beside the bank', (t) async {
    await _pump(
      t,
      _today({'banked': 26, 'prepaid': 15, 'own_minutes': 2, 'lc_minutes': 1}),
    );
    expect(bySpoken('Credited 15/15 min'), findsOneWidget);
    expect(bySpoken('Banked 26 min · prepaid 15'), findsOneWidget);
    expect(bySpoken('2 min own work today'), findsOneWidget);
    expect(bySpoken('1 min LeetCode today'), findsOneWidget);
    expect(_stat(Icons.person_outline, '2'), findsOneWidget);
    expect(_stat(Icons.code, '1'), findsOneWidget);
    // One hover word each, not spoken twice.
    expect(find.byTooltip('Own'), findsOneWidget);
    expect(find.byTooltip('LeetCode'), findsOneWidget);
  });

  testWidgets('zero, or an older worker, shows neither', (t) async {
    await _pump(t, _today({'own_minutes': 0, 'lc_minutes': 0}));
    expect(find.byIcon(Icons.person_outline), findsNothing);
    expect(find.byIcon(Icons.code), findsNothing);
    await _pump(t, _today({}));
    expect(find.byIcon(Icons.person_outline), findsNothing);
    expect(find.byIcon(Icons.code), findsNothing);
    expect(bySpoken('Credited 15/15 min'), findsOneWidget);
  });

  testWidgets('each shows alone', (t) async {
    await _pump(t, _today({'lc_minutes': 4}));
    expect(_stat(Icons.code, '4'), findsOneWidget);
    expect(find.byIcon(Icons.person_outline), findsNothing);
    await _pump(t, _today({'own_minutes': 7}));
    expect(_stat(Icons.person_outline, '7'), findsOneWidget);
    expect(find.byIcon(Icons.code), findsNothing);
  });
}
