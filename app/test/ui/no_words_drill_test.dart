// textgate guard, the drill: question, wrong, right, empty and failed paint
// no app words (the other learning screens: no_words_learn_test.dart).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/drill/anki_sync.dart';
import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/ui/review_screen.dart';

import '../support/drill.dart';
import '../support/fake_stream.dart';
import '../support/learn_finders.dart';
import '../support/no_words.dart';
import '../support/ui.dart';

const _phone = Size(412, 900);
const _wide = Size(1100, 2400);

void main() {
  for (final size in [_phone, _wide]) {
    final at = size == _phone ? 'phone' : 'wide';

    testWidgets('drill: question, wrong, right, empty, failed ($at)', (
      t,
    ) async {
      final db = fixtureDb();
      final stream = FakeStream();
      final s = await fixtureServices(db, stream);
      await pumpScreen(
        t,
        ReviewScreen(
          services: s,
          drill: true,
          unavailable: const Unavailable(until: kResetsAt, reason: 'limit'),
          anki: AnkiSync(relay: s.relay, launcher: FakeLauncher()),
        ),
        size: size,
        settle: false,
      );
      await answer(t, db, stream, data: drillQuestion());
      expectNoWords(t, 'drill question + banner + anki');
      await t.tap(find.text('Opens valves'));
      await sent(t);
      await answer(t, db, stream, data: drillGrade(0));
      expectNoWords(t, 'drill wrong');
      await t.tap(spoken('Next (Space)'));
      await sent(t);
      await answer(t, db, stream, data: drillQuestion());
      await t.tap(find.text('Turns pistons into rotation'));
      await sent(t);
      await answer(t, db, stream, data: drillGrade(1));
      expectNoWords(t, 'drill right');
      await t.tap(spoken('Next (Space)'));
      await sent(t);
      await answer(t, db, stream, data: {'empty': true});
      expectNoWords(t, 'drill empty');
      await t.tap(spoken('Review'));
      await t.pumpAndSettle();
      await t.tap(spoken('Drill').last);
      await sent(t);
      await answer(t, db, stream, code: 'worker_error');
      expectNoWords(t, 'drill failed');
    });
  }
}
