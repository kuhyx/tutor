import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/widgets/count_badge.dart';

import '../support/no_words.dart';

Future<void> _pump(WidgetTester t, Widget child) => t.pumpWidget(
  MaterialApp(
    home: Scaffold(body: Center(child: child)),
  ),
);

void main() {
  testWidgets('a badge, a badge on a glyph, a stat and an id chip', (t) async {
    await _pump(
      t,
      Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CountBadge(7, icon: Icons.today),
          const CountBadge(2, color: Colors.red),
          CountBadge.on(const Icon(Icons.mail), count: 4),
          CountBadge.on(const Icon(Icons.mail), count: 0),
          const GlyphStat(Icons.timer, '18', color: Colors.blue, size: 20),
          const IdChip('20261012-170448-5b71'),
          const IdChip('ab'),
        ],
      ),
    );
    expect(find.text('7'), findsOneWidget);
    expect(find.text('4'), findsOneWidget);
    expect(find.text('18'), findsOneWidget);
    // The chip shows the short tail of the id, monospaced.
    final id = t.widget<Text>(find.text('5b71'));
    expect(id.style?.fontFamily, 'monospace');
    expect(find.text('ab'), findsOneWidget);
    expectNoWords(t, 'badges');
  });
}
