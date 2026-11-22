// A past session's Repeat can be blocked (`locked`): as in the Session,
// the gate's review opens at once, never a status line or a button.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/transcript_screen.dart';

import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

const _sid = '20261011-090000-a1b2';

void main() {
  testWidgets('Repeat -> locked -> the review opens', (t) async {
    final db = fixtureDb();
    db.root = setAt(db.root, 'tutor/v1-e2e/sessions/$_sid/msgs', {
      'm0001': {'role': 'tutor', 'text': 'Earlier turn'},
    });
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await s.events.record(
      TaughtEvent(subject: 'car', card: 'fuel-spark', at: fixtureNow),
    );
    await pumpScreen(t, TranscriptScreen(services: s, sid: _sid));
    await t.tap(controlByLabel('Repeat'));
    await sent(t);
    await answer(
      t,
      db,
      stream,
      code: 'locked',
      error: 'raw worker text',
      extra: const {
        'subject_id': 'car',
        'next': 'review_module',
        'module': 'fuel',
        'module_title': 'Fuel and ignition',
        'gate_cards': ['fuel-spark'],
      },
    );
    for (var i = 0; i < 10; i++) {
      await t.pump(const Duration(milliseconds: 100));
    }
    expect(cueContaining('raw worker text'), findsNothing);
    expect(controlByLabel('Review Fuel and ignition'), findsNothing);
    expect(controlByLabel('Review: Fuel and ignition'), findsOneWidget);
  });
}
