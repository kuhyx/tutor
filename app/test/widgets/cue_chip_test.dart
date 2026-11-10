import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../support/no_words.dart';

Widget _app(Widget child, {bool noAnimations = false}) => MaterialApp(
  builder: (context, c) => MediaQuery(
    data: MediaQuery.of(context).copyWith(disableAnimations: noAnimations),
    child: c!,
  ),
  home: Scaffold(body: Center(child: child)),
);

void main() {
  test('every kind has a glyph and a tint', () {
    for (final k in CueKind.values) {
      expect(cueIcon(k), isA<IconData>());
    }
    expect(cueIcon(CueKind.error), Icons.error_outline);
  });

  testWidgets('an error shakes once, then stands still', (t) async {
    await t.pumpWidget(
      _app(const CueChip(kind: CueKind.error, semanticLabel: 'Failed')),
    );
    await t.pump(const Duration(milliseconds: 100));
    expect(t.hasRunningAnimations, isTrue);
    final moved = t
        .widgetList<Transform>(find.byType(Transform))
        .any((x) => x.transform.getTranslation().x.abs() > 0.01);
    expect(moved, isTrue);
    await t.pumpAndSettle();
    expect(t.hasRunningAnimations, isFalse);
    expect(find.byIcon(Icons.error_outline), findsOneWidget);
    expectNoWords(t, 'error cue');
  });

  testWidgets('no shake when animations are off; a new error shakes', (
    t,
  ) async {
    await t.pumpWidget(
      _app(
        const CueChip(kind: CueKind.error, semanticLabel: 'a'),
        noAnimations: true,
      ),
    );
    await t.pump(const Duration(milliseconds: 100));
    expect(t.hasRunningAnimations, isFalse);

    await t.pumpWidget(
      _app(const CueChip(kind: CueKind.error, semanticLabel: 'a')),
    );
    await t.pumpAndSettle();
    await t.pumpWidget(
      _app(const CueChip(kind: CueKind.error, semanticLabel: 'b')),
    );
    await t.pump(const Duration(milliseconds: 50));
    expect(t.hasRunningAnimations, isTrue);
    await t.pumpAndSettle();
  });

  testWidgets('pending spins, others show their glyph, trailing shows', (
    t,
  ) async {
    await t.pumpWidget(
      _app(
        const Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CueChip(kind: CueKind.pending, semanticLabel: 'busy'),
            CueChip(
              kind: CueKind.blocked,
              icon: Icons.replay,
              semanticLabel: 'blocked',
            ),
            CueChip(
              kind: CueKind.ok,
              semanticLabel: 'ok',
              trailing: [Icon(Icons.close)],
            ),
            CueChip(kind: CueKind.offline, semanticLabel: 'off'),
          ],
        ),
      ),
    );
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.byIcon(Icons.replay), findsOneWidget);
    expect(find.byIcon(Icons.check_circle_outline), findsOneWidget);
    expect(find.byIcon(Icons.close), findsOneWidget);
    expect(find.byIcon(Icons.cloud_off), findsOneWidget);
    expectNoWords(t, 'cues');
  });
}
