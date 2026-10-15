// The keyboard-open fold of the tutor's latest message: exactly one rendered
// line (the last non-blank one, cut with an ellipsis), a tap shows it all.
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/ui/session/collapsed_tile.dart';

const _last =
    'Last paragraph that is long enough to wrap over several lines on a '
    'narrow phone: which **valve** closes first, and why does the camshaft '
    'lobe decide it rather than the piston?';

Future<void> _pump(WidgetTester t) => t.pumpWidget(
  const MaterialApp(
    home: Scaffold(
      body: Center(
        child: SizedBox(
          width: 300,
          child: CollapsedTile(
            message: Message(role: 'tutor', text: 'First.\n\n$_last\n'),
            full: Text('FULL TILE'),
          ),
        ),
      ),
    ),
  ),
);

void main() {
  testWidgets('collapsed: the last line on exactly one rendered line', (
    t,
  ) async {
    await _pump(t);
    final line = find.byKey(const ValueKey('collapsed-line'));
    final text = t.widget<Text>(line);
    expect(text.maxLines, 1);
    expect(text.overflow, TextOverflow.ellipsis);
    expect(find.textContaining('First.', findRichText: true), findsNothing);
    expect(find.textContaining('narrow phone', findRichText: true), findsOne);

    final p = t.renderObject<RenderParagraph>(
      find.descendant(of: line, matching: find.byType(RichText)),
    );
    expect(p.didExceedMaxLines, isTrue); // long enough that it would wrap
    final oneLine = p.getFullHeightForCaret(const TextPosition(offset: 0));
    expect(p.size.height, closeTo(oneLine, 0.5));

    await t.tap(find.byIcon(Icons.expand_more));
    await t.pumpAndSettle();
    expect(find.text('FULL TILE'), findsOneWidget);
    expect(line, findsNothing);
  });
}
