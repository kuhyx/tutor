// A reply that never lands must not block Send forever (fake time).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

const _base = 'tutor/v1/sessions/$fixtureLiveSid';

/// Feeds the screen's listens from [db] (live, meta, msgs).
Future<void> _feed(WidgetTester t, FakeRtdb db, FakeStream stream) async {
  for (final path in ['tutor/v1/live', '$_base/meta', '$_base/msgs']) {
    stream.emit(path, RtdbPut('/', getAt(db.root, path)));
    await t.pump();
  }
  await t.pump();
}

void main() {
  testWidgets('no reply for 3 minutes: Send reopens, text kept, same rid', (
    t,
  ) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      SessionScreen(services: s),
      size: const Size(1366, 1500), // Send stays on screen under the status
      settle: false,
    );
    await _feed(t, db, stream);
    await t.pumpAndSettle();
    final box = fieldByLabel('Your answer').first;
    final send = controlByLabel('Send');
    const stalled = 'No reply from PC — send again';
    await t.enterText(box, 'power');
    await t.pump();
    await t.tap(send);
    await sent(t);
    final (rid, _) = lastRequest(db);
    expect(pressOf(t, 'Send'), isNull);
    expect(cueLabelled(stalled), findsNothing);

    await t.pump(const Duration(minutes: 2, seconds: 59));
    expect(cueLabelled(stalled), findsNothing);
    await t.pump(const Duration(seconds: 1));
    expect(cueLabelled(stalled), findsOneWidget);
    expect(pressOf(t, 'Send'), isNotNull);
    expect(t.widget<TextField>(box).controller!.text, 'power');

    // Send again: the SAME request (the worker dedupes it by rid), so a
    // reply that was only late lands once.
    await t.tap(send);
    await sent(t);
    final reqs = getAt(db.root, 'tutor/v1/requests')! as Map<String, dynamic>;
    expect(reqs.keys, [rid]);
    expect(cueLabelled(stalled), findsNothing);
    expect(pressOf(t, 'Send'), isNull);
    await answer(t, db, stream, data: {'msg': 'm0005'});
    expect(t.widget<TextField>(box).controller!.text, '');
    expect(cueLabelled(stalled), findsNothing);
  });
}
