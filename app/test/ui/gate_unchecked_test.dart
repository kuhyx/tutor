// The module gate held by cards read without Claude (plan e79be0be-0 step 5,
// mockup F5): the worker names them in `gate_unchecked`. A review never
// passes them, so the app opens no review and resends nothing; it lists
// them, each with the "unchecked" glyph, and its Start opens a Claude
// session on the subject, which checks them first.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/relay/blocked.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/review_screen.dart';
import 'package:tutor/ui/session/session_screen.dart';
import 'package:tutor/ui/session/unchecked_gate.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

const _pc = '9c1d2e3f-4a5b-4c6d-8e7f-0a1b2c3d4e5f';

Map<String, Object> _gate(List<String> cards, List<String> unchecked) => {
  'subject_id': 'car',
  'subject_title': 'How a car works',
  'next': 'review_module',
  'module': 'engine',
  'module_title': 'The four-stroke engine',
  'gate_cards': cards,
  'gate_unchecked': unchecked,
  'writing': false,
};

/// The car Session, Continue sent; eng-strokes and eng-crank taught at
/// -1 min, eng-crank also passed (a Good review) and marked unchecked.
Future<(FakeRtdb, FakeStream)> _open(WidgetTester t) async {
  final db = fixtureDb();
  final at = fixtureNow - 60000;
  final rows = [
    {'k': 'taught', 's': 'car', 'c': 'eng-strokes', 'at': at},
    {'k': 'taught', 's': 'car', 'c': 'eng-crank', 'at': at},
    {'k': 'review', 's': 'car', 'c': 'eng-crank', 'at': at + 1, 'g': 3},
    {'k': 'unchecked', 's': 'car', 'c': 'eng-crank', 'at': at + 2},
  ];
  for (final (n, row) in rows.indexed) {
    db.root = setAt(
      db.root,
      'tutor/v1-e2e/log/$_pc/01JA000000000000000000000$n',
      row,
    );
  }
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
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

Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 10; i++) {
    await t.pump(const Duration(milliseconds: 100));
  }
}

int _requests(FakeRtdb db) =>
    (getAt(db.root, 'tutor/v1-e2e/requests') as Map?)?.length ?? 0;

void main() {
  test('gate_unchecked parses; only-unchecked holds the gate', () {
    final held = Blocked.fromResult({
      'code': 'no_card_left',
      ..._gate(['eng-crank'], ['eng-crank']),
    });
    expect(held.gateUnchecked, ['eng-crank']);
    expect(held.heldUnchecked, isTrue);
    final mixed = Blocked.fromResult({
      'code': 'no_card_left',
      ..._gate(['eng-strokes', 'eng-crank'], ['eng-crank']),
    });
    expect(mixed.heldUnchecked, isFalse);
    final old = Blocked.fromResult({
      'code': 'no_card_left',
      'gate_cards': ['eng-crank'],
    });
    expect(old.gateUnchecked, isEmpty);
    expect(old.heldUnchecked, isFalse);
    expect(const Blocked().heldUnchecked, isFalse);
  });

  testWidgets('only unchecked cards: the list opens, no review, no resend', (
    t,
  ) async {
    final (db, stream) = await _open(t);
    await answer(
      t,
      db,
      stream,
      code: 'no_card_left',
      extra: _gate(['eng-crank'], ['eng-crank']),
      settle: false,
    );
    await _settle(t);
    final before = _requests(db);
    expect(find.byType(UncheckedGateScreen), findsOneWidget);
    expect(find.byType(ReviewScreen), findsNothing);
    expect(find.text('What does the crankshaft do?'), findsOneWidget);
    expect(find.byIcon(Icons.pending_actions), findsWidgets);
    expect(find.byTooltip('Unchecked'), findsWidgets);
    expect(bySpoken('Waiting for Claude’s check'), findsOneWidget);
    // Back: one glyph on the Session, which reopens the list.
    await t.pageBack();
    await _settle(t);
    expect(_requests(db), before);
    final glyph = controlByLabel('1 cards wait for Claude’s check');
    expect(glyph, findsOneWidget);
    await t.tap(glyph);
    await sent(t);
    expect(_requests(db), before + 1);
    await answer(
      t,
      db,
      stream,
      code: 'no_card_left',
      extra: _gate(['eng-crank'], ['eng-crank']),
      settle: false,
    );
    await _settle(t);
    expect(find.byType(UncheckedGateScreen), findsOneWidget);
  });

  testWidgets('its Start opens a Claude session on the subject', (t) async {
    final (db, stream) = await _open(t);
    await answer(
      t,
      db,
      stream,
      code: 'no_card_left',
      extra: _gate(['eng-crank'], ['eng-crank']),
      settle: false,
    );
    await _settle(t);
    await t.tap(controlByLabel('Check with Claude'));
    await _settle(t);
    expect(find.byType(UncheckedGateScreen), findsNothing);
    final (_, req) = lastRequest(db);
    expect(req['kind'], 'session_start');
    expect(req['body'], {
      'subject': 'car',
      'card': null,
      'resume': true,
      'device': 'desktop',
    });
  });

  testWidgets('unreviewed cards beside them: the review opens first', (
    t,
  ) async {
    final (db, stream) = await _open(t);
    await answer(
      t,
      db,
      stream,
      code: 'no_card_left',
      extra: _gate(['eng-strokes', 'eng-crank'], ['eng-crank']),
      settle: false,
    );
    await _settle(t);
    expect(find.byType(ReviewScreen), findsOneWidget);
    expect(find.byType(UncheckedGateScreen), findsNothing);
  });
}
