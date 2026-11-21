// The blocked panel draws a result without words: no_card_left draws its due
// time and module, a locked review its replay glyph, and a red failure never
// speaks the worker's sentence (the kinds themselves: relay_kinds_test.dart).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/progress/terms.dart';
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

/// Everything painted inside the block's cue, letters and digits only.
String _paintedInCue(WidgetTester t) {
  final cue = find.descendant(
    of: find.byType(BlockedPanel),
    matching: find.byType(CueChip),
  );
  return t
      .widgetList<RichText>(
        find.descendant(of: cue, matching: find.byType(RichText)),
      )
      .map((r) => r.text.toPlainText())
      .join()
      .replaceAll(RegExp(r'[^\p{L}\p{N}]', unicode: true), '');
}

void main() {
  testWidgets('no_card_left due: clock glyph plus a ring, no text', (t) async {
    final due = fixtureNow + const Duration(hours: 6).inMilliseconds;
    await _blocked(t, 'no_card_left', {
      'subject_title': 'How a car works',
      'next': 'reviews_due',
      'due_at': due,
    });
    expect(find.byIcon(Icons.schedule), findsOneWidget);
    final ring = t.widget<DueRing>(find.byType(DueRing));
    expect(ring.dueAt, due);
    expect(
      find.descendant(
        of: find.byType(BlockedPanel),
        matching: find.byType(Text),
      ),
      findsNothing,
    );
    expect(_paintedInCue(t), isEmpty);
    expect(cueLabelled('No card left', prefix: true), findsOneWidget);
    expect(cueLabelled(_sentinel, prefix: true), findsNothing);
  });

  testWidgets('no_card_left review: the module mark, tappable', (t) async {
    await _blocked(t, 'no_card_left', {
      'subject_title': 'How a car works',
      'next': 'review_module',
      'module': 'fuel',
      'module_title': 'Fuel and ignition',
    });
    final cue = find.descendant(
      of: find.byType(BlockedPanel),
      matching: find.byType(CueChip),
    );
    final mark = find.descendant(
      of: cue,
      matching: find.byType(ModuleMarkIcon),
    );
    expect(mark, findsOneWidget);
    expect(t.widget<ModuleMarkIcon>(mark).mark, ModuleMark.done);
    expect(_paintedInCue(t), isEmpty);
    await t.tap(mark);
    await sent(t);
    await sent(t);
    expect(controlByLabel('Review: Fuel and ignition'), findsOneWidget);
  });

  testWidgets('locked review: tapping the replay glyph opens the review', (
    t,
  ) async {
    await _blocked(t, 'locked', {
      'subject_title': 'How a car works',
      'next': 'review_module',
      'module': 'fuel',
      'module_title': 'Fuel and ignition',
    });
    expect(find.byIcon(Icons.replay), findsOneWidget);
    expect(_paintedInCue(t), isEmpty);
    await t.tap(find.byIcon(Icons.replay));
    await sent(t);
    await sent(t);
    expect(controlByLabel('Review: Fuel and ignition'), findsOneWidget);
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
