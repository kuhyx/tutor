import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/widgets/spoken_label.dart';

import '../support/label_finders.dart';
import '../support/no_words.dart';

Future<void> _pump(WidgetTester t, Widget child) => t.pumpWidget(
  MaterialApp(
    home: Scaffold(body: Center(child: child)),
  ),
);

void main() {
  testWidgets('a glyph button taps, is spoken, shows a badge, no words', (
    t,
  ) async {
    var taps = 0;
    await _pump(
      t,
      GlyphButton(
        icon: Icons.style,
        semanticLabel: 'Review (3 due)',
        count: 3,
        onPressed: () => taps++,
      ),
    );
    final h = t.ensureSemantics();
    expect(find.bySemanticsLabel('Review (3 due)'), findsOneWidget);
    h.dispose();
    expect(find.text('3'), findsOneWidget);
    await t.tap(glyphsLabelled('Review (3 due)'));
    expect(taps, 1);
    expectNoWords(t, 'glyph button');
  });

  testWidgets('disabled, filled, selected and tinted variants', (t) async {
    await _pump(
      t,
      const Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          GlyphButton(
            icon: Icons.check,
            semanticLabel: 'Done',
            onPressed: null,
          ),
          GlyphButton(
            icon: Icons.check,
            semanticLabel: 'Go',
            onPressed: _noop,
            filled: true,
            tint: Colors.red,
            selected: true,
            size: 20,
          ),
        ],
      ),
    );
    expect(pressOf(t, 'Done'), isNull);
    expect(pressOf(t, 'Go'), isNotNull);
    expect(find.byType(IconButton), findsNWidgets(2));
  });

  testWidgets('a spoken label can carry the live-region flag', (t) async {
    await _pump(
      t,
      const SpokenLabel(
        semanticLabel: 'Saved',
        liveRegion: true,
        child: Icon(Icons.check),
      ),
    );
    final h = t.ensureSemantics();
    final node = t.getSemantics(find.byType(SpokenLabel));
    expect(node.label, 'Saved');
    h.dispose();
  });
}

void _noop() {}
