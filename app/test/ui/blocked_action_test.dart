// A blocking result is one glyph, never a panel of chips and buttons
// (kuhy, 2026-11-22): cards to review open their review at once, a locked
// later module opens the earlier module's review, and nothing to do is a
// single calm glyph that leads Home. No red, never the worker's raw text.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/session/session_screen.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

const _pc = '9c1d2e3f-4a5b-4c6d-8e7f-0a1b2c3d4e5f';

/// The car Session as Continue learning opens it (pushed over a Home
/// stand-in), answered [code]; the engine cards taught by the PC.
Future<FakeRtdb> _blocked(
  WidgetTester t,
  String code,
  Map<String, Object?> extra,
) async {
  final db = fixtureDb();
  var n = 0;
  for (final c in ['eng-strokes', 'eng-crank', 'fuel-spark']) {
    db.root = setAt(
      db.root,
      'tutor/v1-e2e/log/$_pc/01JA000000000000000000000${n++}',
      {'k': 'taught', 's': 'car', 'c': c, 'at': fixtureNow - 60000},
    );
  }
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  await pumpScreen(
    t,
    Builder(
      builder: (context) => TextButton(
        onPressed: () => Navigator.of(context).push(
          MaterialPageRoute<void>(
            builder: (_) => SessionScreen(
              services: s,
              subject: 'car',
              resume: true,
              now: () => DateTime.fromMillisecondsSinceEpoch(fixtureNow),
            ),
          ),
        ),
        child: const Icon(Icons.home),
      ),
    ),
  );
  await t.tap(find.byIcon(Icons.home));
  await sent(t);
  await sent(t);
  await answer(
    t,
    db,
    stream,
    code: code,
    error: 'raw worker text',
    extra: extra,
    settle: false,
  );
  for (var i = 0; i < 10; i++) {
    await t.pump(const Duration(milliseconds: 100));
  }
  return db;
}

void main() {
  testWidgets('a locked later module opens the earlier review', (t) async {
    await _blocked(t, 'locked', {
      'subject_id': 'car',
      'subject_title': 'How a car works',
      'next': 'review_module',
      'module': 'engine',
      'module_title': 'The four-stroke engine',
      'gate_cards': ['eng-strokes', 'eng-crank'],
    });
    expect(controlByLabel('Review: The four-stroke engine'), findsOneWidget);
    expect(controlByLabel('2 left'), findsOneWidget);
  });

  testWidgets('every module done, reviews due: the due review opens', (
    t,
  ) async {
    await _blocked(t, 'no_card_left', {
      'subject_id': 'car',
      'subject_title': 'How a car works',
      'next': 'reviews_due',
      'due_at': fixtureNow - 1000,
      'gate_cards': ['fuel-spark'],
    });
    expect(controlByLabel('Review: How a car works'), findsOneWidget);
    expect(controlByLabel('1 left'), findsOneWidget);
  });

  testWidgets('locked, nothing to do: one calm glyph that goes Home', (
    t,
  ) async {
    final db = await _blocked(t, 'locked', const {
      'subject_id': 'car',
      'next': 'none',
      'gate_cards': <String>[],
    });
    expect(cueOfKind(CueKind.error), findsNothing);
    expect(find.byType(CueChip), findsNothing);
    expect(bySpoken('raw worker text', prefix: true), findsNothing);
    expect(
      bySpoken('That is locked until earlier modules are reviewed.'),
      findsOneWidget,
    );
    await t.tap(find.byTooltip('Done'));
    for (var i = 0; i < 10; i++) {
      await t.pump(const Duration(milliseconds: 100));
    }
    expect(find.byType(SessionScreen), findsNothing); // Home again
    expect(getAt(db.root, 'tutor/v1-e2e/prefs/current_subject'), 'car');
  });
}
