// A past session's Repeat can be blocked (`locked`): the same call to
// action as the Session, not a status line.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/transcript_screen.dart';

import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

const _sid = '20261011-090000-a1b2';

void main() {
  testWidgets('Repeat -> locked -> Review <module>', (t) async {
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
        'next': 'review_module',
        'module': 'fuel',
        'module_title': 'Fuel and ignition',
      },
    );
    expect(
      cueLabelled('That is locked until “Fuel and ignition” is reviewed.'),
      findsOneWidget,
    );
    expect(cueContaining('raw worker text'), findsNothing);
    await t.tap(controlByLabel('Review Fuel and ignition'));
    await t.pumpAndSettle();
    expect(controlByLabel('Review: Fuel and ignition'), findsOneWidget);
  });
}
