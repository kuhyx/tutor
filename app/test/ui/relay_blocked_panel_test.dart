// The blocked panel draws a result without words: no_card_left draws one
// ring for its due time, and a red failure never speaks the worker's
// sentence (the kinds themselves: relay_kinds_test.dart).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/learn_bits.dart';
import 'package:tutor/ui/relay_cue.dart';
import 'package:tutor/ui/session/blocked_panel.dart';
import 'package:tutor/ui/session/session_screen.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

const _sentinel = 'SERVER-SENTENCE-7f3a';

Future<(FakeRtdb, FakeStream)> _blocked(
  WidgetTester t,
  String code,
  Map<String, Object?> extra,
) async {
  final db = fixtureDb();
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  await pumpScreen(
    t,
    SessionScreen(services: s, subject: 'car', resume: true),
    settle: false,
  );
  await sent(t);
  await answer(
    t,
    db,
    stream,
    code: code,
    error: _sentinel,
    extra: extra,
    settle: false,
  );
  await sent(t);
  return (db, stream);
}

/// Everything painted inside the block's glyph, letters and digits only.
String _painted(WidgetTester t) {
  return t
      .widgetList<RichText>(
        find.descendant(
          of: find.byType(BlockedPanel),
          matching: find.byType(RichText),
        ),
      )
      .map((r) => r.text.toPlainText())
      .join()
      .replaceAll(RegExp(r'[^\p{L}\p{N}]', unicode: true), '');
}

void main() {
  testWidgets('no_card_left due: one ring, no text', (t) async {
    final due = DateTime.now()
        .add(const Duration(hours: 6))
        .millisecondsSinceEpoch;
    await _blocked(t, 'no_card_left', {
      'subject_title': 'How a car works',
      'next': 'reviews_due',
      'due_at': due,
    });
    final ring = t.widget<DueRing>(find.byType(DueRing));
    expect(ring.dueAt, due);
    expect(
      find.descendant(
        of: find.byType(BlockedPanel),
        matching: find.byType(Text),
      ),
      findsNothing,
    );
    expect(_painted(t), isEmpty);
    expect(bySpoken('No card left', prefix: true), findsOneWidget);
    expect(bySpoken(_sentinel, prefix: true), findsNothing);
  });

  // The gated refusals open their review by themselves (gate_flow_test,
  // blocked_action_test); without gate cards nothing is tappable to review.
  testWidgets('review_module, no gate cards: no module mark, no replay', (
    t,
  ) async {
    await _blocked(t, 'no_card_left', {
      'subject_title': 'How a car works',
      'next': 'review_module',
      'module': 'fuel',
      'module_title': 'Fuel and ignition',
    });
    expect(find.byType(ModuleMarkIcon), findsNothing);
    expect(find.byIcon(Icons.replay), findsNothing);
    expect(find.byType(CueChip), findsNothing);
    expect(controlByLabel('Review: Fuel and ignition'), findsNothing);
  });

  testWidgets('a red failure speaks the app sentence, never the worker', (
    t,
  ) async {
    await _blocked(t, 'model_error', const {});
    expect(find.byIcon(kindIcon('err_model')), findsOneWidget);
    expect(cueOfKind(CueKind.error), findsOneWidget);
    final semantics = t.ensureSemantics();
    expect(find.bySemanticsLabel(RegExp(_sentinel)), findsNothing);
    semantics.dispose();
  });
}
