import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/coach/coach_postmortem.dart';

import '../../coach/coach_fixtures.dart';
import '../../support/fake_rtdb.dart';
import '../../support/fake_stream.dart';
import '../../support/services.dart';
import '../../support/ui.dart';

void main() {
  late FakeRtdb db;
  late FakeStream stream;

  Future<void> open(WidgetTester t, {String? summary}) async {
    db = FakeRtdb();
    stream = FakeStream();
    await pumpScreen(
      t,
      CoachPostMortemScreen(
        services: services(db, stream),
        lcId: lcId,
        summaryMd: summary,
      ),
      settle: false,
    );
    await t.pump(const Duration(milliseconds: 50));
  }

  Map<String, dynamic> body() =>
      lastRequest(db).$2['body'] as Map<String, dynamic>;

  Future<void> tap(WidgetTester t, String key) async {
    await t.ensureVisible(find.byKey(ValueKey(key)));
    await t.tap(find.byKey(ValueKey(key)));
    await sent(t);
  }

  testWidgets('asks for the cards, shows them, the Anki line, refusals', (
    t,
  ) async {
    await open(t, summary: '| step | rung |\n| --- | --- |\n| 1 | H0 |');
    expect(lastRequest(db).$2['kind'], 'lc_cards');
    expect(body(), {'lc_id': lcId});
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    await answer(t, db, stream, data: cardsData, settle: false);
    await t.pump(const Duration(milliseconds: 100));
    expect(find.text('rung'), findsOneWidget);
    expect(find.text('Toolbox: one pass, O(1) lookup?'), findsOneWidget);
    expect(find.text('hash map'), findsOneWidget);
    expect(find.byIcon(Icons.fiber_new_outlined), findsOneWidget);
    expect(find.text('nests with hash map'), findsOneWidget);
    expect(find.text('Anki is closed'), findsOneWidget);
    expect(find.text('conditional aggregation'), findsOneWidget);
  });

  testWidgets('an already known card is not marked new', (t) async {
    await open(t);
    await answer(
      t,
      db,
      stream,
      data: {
        'cards': [
          {'id': 'a', 'front': 'f', 'back': 'b'},
        ],
      },
      settle: false,
    );
    await t.pump(const Duration(milliseconds: 100));
    expect(find.byIcon(Icons.fiber_new_outlined), findsNothing);
    expect(find.byIcon(Icons.style_outlined), findsWidgets);
    expect(find.byKey(const ValueKey('confirm-cards')), findsNothing);
  });

  testWidgets('confirming sends the checked entries, skipped ones stay out', (
    t,
  ) async {
    await open(t);
    await answer(t, db, stream, data: cardsData, settle: false);
    await t.pump(const Duration(milliseconds: 100));
    await tap(t, 'proposal-quoting');
    await tap(t, 'confirm-cards');
    expect(body(), {
      'lc_id': lcId,
      'confirm': [
        {
          'name': 'conditional aggregation',
          'aliases': ['sum case'],
          'properties': ['per-row branch', 'collapse rows'],
        },
      ],
    });
    await answer(t, db, stream, settle: false);
    await t.pump(const Duration(milliseconds: 100));
    expect(find.byKey(const ValueKey('confirm-cards')), findsNothing);
  });

  testWidgets(
    'skipping everything disables the button; a tick brings it back',
    (t) async {
      await open(t);
      await answer(t, db, stream, data: cardsData, settle: false);
      await t.pump(const Duration(milliseconds: 100));
      await tap(t, 'proposal-quoting');
      await tap(t, 'proposal-conditional aggregation');
      expect(
        t
            .widget<FilledButton>(find.byKey(const ValueKey('confirm-cards')))
            .onPressed,
        isNull,
      );
      await tap(t, 'proposal-quoting');
      expect(
        t
            .widget<FilledButton>(find.byKey(const ValueKey('confirm-cards')))
            .onPressed,
        isNotNull,
      );
    },
  );

  testWidgets('an error shows with Retry; a damaged result shows why', (
    t,
  ) async {
    await open(t);
    await answer(t, db, stream, code: 'model_error', extra: {'retry': true});
    expect(find.text('Retry'), findsOneWidget);
    await t.tap(find.text('Retry'));
    await sent(t);
    await answer(t, db, stream, data: {'cards': 3}, settle: false);
    await t.pump(const Duration(milliseconds: 100));
    expect(find.textContaining('expected array'), findsOneWidget);
  });
}
