import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/ui.dart';
import '_data.dart';
import '_panel_harness.dart';

void main() {
  final h = PanelHarness();

  testWidgets('focus_refused is loud: its kind glyph, the app sentence', (
    t,
  ) async {
    final sem = t.ensureSemantics();
    await h.open(t, interviewProject());
    h.prompts.score = 10;
    await t.tap(h.key('mock'));
    await sent(t);
    await answer(
      t,
      h.db,
      h.stream,
      code: 'focus_refused',
      error: 'mock needs a score of at least 0',
      settle: false,
    );
    await sent(t);
    final err = find.byKey(const ValueKey('interview-error'));
    expect(err, findsOneWidget);
    expect(
      find.descendant(of: err, matching: find.byIcon(Icons.do_not_disturb_alt)),
      findsOneWidget,
    );
    expect(
      find.bySemanticsLabel('The focus project was refused.'),
      findsOneWidget,
    );
    expect(
      find.bySemanticsLabel(RegExp('mock needs a score')),
      findsNothing,
      reason: 'the worker words are never spoken',
    );
    expect(
      find.descendant(of: err, matching: find.byType(Text)),
      findsNothing,
      reason: 'icon + state, no visible words',
    );
    expect(h.colorOf(t, 'mock'), isNot(AppPalette.success));
    sem.dispose();
  });

  testWidgets('an error clears when the next action succeeds', (t) async {
    await h.open(t, interviewProject());
    h.prompts.score = 10;
    await t.tap(h.key('mock'));
    await sent(t);
    await answer(t, h.db, h.stream, code: 'focus_refused', settle: false);
    await sent(t);
    expect(find.byKey(const ValueKey('interview-error')), findsOneWidget);
    await t.tap(h.key('mock'));
    await sent(t);
    await answer(
      t,
      h.db,
      h.stream,
      data: block([ms('mock', '2026-11-18T23:59:00', 'done')]),
      settle: false,
    );
    await sent(t);
    expect(find.byKey(const ValueKey('interview-error')), findsNothing);
    expect(h.colorOf(t, 'mock'), AppPalette.success);
  });
}
