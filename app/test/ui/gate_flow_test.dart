// The module gate in the Session (kuhy, 2026-11-22): a refusal naming
// `gate_cards` opens that review at once (no chip, no book button); passing
// every card sends the same request again with no extra click; leaving
// early leaves one review glyph that reopens it; nothing to do is one glyph
// and a refused Next shakes.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/session/session_bits.dart';
import 'package:tutor/ui/session/session_screen.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/spoken_label.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

const _pc = '9c1d2e3f-4a5b-4c6d-8e7f-0a1b2c3d4e5f';

const Map<String, Object> _gate = {
  'subject_id': 'car',
  'subject_title': 'How a car works',
  'next': 'review_module',
  'module': 'engine',
  'module_title': 'The four-stroke engine',
  'gate_cards': ['eng-strokes', 'eng-crank'],
  'writing': false,
};

/// The car Session, Continue sent; two engine cards the PC taught at -1 min.
Future<(FakeRtdb, FakeStream)> _open(
  WidgetTester t, {
  Future<void> Function(TutorServices s)? before,
}) async {
  final db = fixtureDb();
  final at = fixtureNow - 60000;
  var n = 0;
  for (final c in ['eng-strokes', 'eng-crank']) {
    db.root = setAt(
      db.root,
      'tutor/v1-e2e/log/$_pc/01JA000000000000000000000${n++}',
      {'k': 'taught', 's': 'car', 'c': c, 'at': at},
    );
  }
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  await before?.call(s);
  await pumpScreen(
    t,
    SessionScreen(
      services: s,
      subject: 'car',
      resume: true,
      now: () => DateTime.fromMillisecondsSinceEpoch(fixtureNow),
    ),
    settle: false,
  );
  await sent(t);
  return (db, stream);
}

Future<void> _passAll(WidgetTester t, int n) async {
  for (var i = 0; i < n; i++) {
    await t.tap(controlByLabel('Show answer (Space)'));
    await _settle(t);
    await t.tap(controlByLabel('3 Good'));
    await _settle(t);
  }
}

// A request in flight spins forever: pump a while instead of settling.
Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 10; i++) {
    await t.pump(const Duration(milliseconds: 100));
  }
}

int _requests(FakeRtdb db) =>
    (getAt(db.root, 'tutor/v1-e2e/requests') as Map?)?.length ?? 0;

void main() {
  testWidgets('a gated refusal opens the review at once', (t) async {
    final (db, stream) = await _open(t);
    await answer(t, db, stream, code: 'no_card_left', extra: _gate);
    expect(controlByLabel('Review: The four-stroke engine'), findsOneWidget);
    expect(controlByLabel('2 left'), findsOneWidget);
    // Never the old panel: no chip, no book button.
    expect(find.byType(CueChip), findsNothing);
    expect(find.byIcon(Icons.menu_book_outlined), findsNothing);
  });

  testWidgets('passing every card sends the request again, no click', (
    t,
  ) async {
    final (db, stream) = await _open(t);
    final (_, first) = lastRequest(db);
    await answer(t, db, stream, code: 'no_card_left', extra: _gate);
    final before = _requests(db);
    await _passAll(t, 2);
    await sent(t);
    expect(controlByLabel('Review: The four-stroke engine'), findsNothing);
    expect(_requests(db), before + 1);
    final (_, again) = lastRequest(db);
    expect(again['kind'], first['kind']);
    // Both ratings reached the log before the request went out.
    final mine = getAt(db.root, 'tutor/v1-e2e/log')! as Map<String, dynamic>;
    final reviews = mine.values
        .expand((d) => (d as Map<String, dynamic>).values)
        .where((e) => (e as Map<String, dynamic>)['k'] == 'review');
    expect(reviews, hasLength(2));
  });

  testWidgets('leaving early leaves one glyph that reopens the review', (
    t,
  ) async {
    final (db, stream) = await _open(t);
    await answer(t, db, stream, code: 'no_card_left', extra: _gate);
    await _passAll(t, 1);
    await t.pageBack();
    await _settle(t);
    expect(controlByLabel('Review: The four-stroke engine'), findsNothing);
    final glyph = find.byTooltip('Review');
    expect(glyph, findsOneWidget);
    await t.tap(glyph);
    await sent(t);
    await answer(
      t,
      db,
      stream,
      code: 'no_card_left',
      extra: _gate,
      settle: false,
    );
    await _settle(t);
    expect(controlByLabel('1 left'), findsOneWidget); // the passed one is out
  });

  testWidgets('nothing to do: one glyph, no buttons; tap goes Home', (t) async {
    final (db, stream) = await _open(t);
    await answer(
      t,
      db,
      stream,
      code: 'no_card_left',
      extra: const {
        'subject_id': 'car',
        'next': 'reviews_due',
        'due_at': 4102444800000,
        'gate_cards': <String>[],
        'writing': false,
      },
      settle: false,
    );
    expect(find.byTooltip('Done'), findsOneWidget);
    expect(find.byType(CueChip), findsNothing);
    expect(controlByLabel('Start session'), findsNothing);
  });

  testWidgets('cards being written: one pencil', (t) async {
    final (db, stream) = await _open(t);
    await answer(
      t,
      db,
      stream,
      code: 'no_card_left',
      extra: const {'subject_id': 'car', 'next': 'none', 'writing': true},
      settle: false,
    );
    expect(find.byTooltip('Writing'), findsOneWidget);
    expect(find.byIcon(Icons.edit), findsOneWidget);
  });

  testWidgets('cards passed meanwhile: one retry, then the glyph, no loop', (
    t,
  ) async {
    final (db, stream) = await _open(
      t,
      before: (s) async {
        for (final c in ['eng-strokes', 'eng-crank']) {
          await s.events.record(
            ReviewEvent(
              subject: 'car',
              card: c,
              grade: Grade.good,
              at: fixtureNow - 1000,
              rev: 1,
            ),
          );
        }
      },
    );
    await answer(
      t,
      db,
      stream,
      code: 'no_card_left',
      extra: _gate,
      settle: false,
    );
    await _settle(t);
    final retried = _requests(db);
    // Never an empty review; the request went out once more.
    expect(controlByLabel('Review: The four-stroke engine'), findsNothing);
    await answer(
      t,
      db,
      stream,
      code: 'no_card_left',
      extra: _gate,
      settle: false,
    );
    await _settle(t);
    expect(_requests(db), retried); // no third try
    expect(find.byTooltip('Review'), findsOneWidget);
  });

  testWidgets('card end: no green check; a refused Next turns amber', (
    t,
  ) async {
    var refused = 0;
    late StateSetter set;
    await pumpScreen(
      t,
      Scaffold(
        body: StatefulBuilder(
          builder: (context, setState) {
            set = setState;
            return CardEnd(onNext: () {}, onStop: () {}, refused: refused);
          },
        ),
      ),
    );
    expect(find.byIcon(Icons.check_circle), findsNothing);
    final plain = t.widget<GlyphButton>(find.byType(GlyphButton).last).tint;
    expect(plain, isNull);
    set(() => refused = 1);
    await t.pump();
    await t.pump(const Duration(milliseconds: 100));
    final moved = t.getTopLeft(find.byType(GlyphButton).last);
    await t.pumpAndSettle();
    expect(t.getTopLeft(find.byType(GlyphButton).last), isNot(moved));
    expect(
      t.widget<GlyphButton>(find.byType(GlyphButton).last).tint,
      isNotNull,
    );
  });
}
