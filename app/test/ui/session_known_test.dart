// The Known concepts (the bar's Known dialog on a wide window) follow the
// catalog and the subject loading late.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/services.dart';
import '../support/ui.dart';

const _base = 'tutor/v1-e2e/sessions/$fixtureLiveSid';
const _rev = 'tutor/v1-e2e/rev';

/// Feeds the screen's listens from [db] (live, meta, msgs).
Future<void> _feed(WidgetTester t, FakeRtdb db, FakeStream stream) async {
  for (final path in ['tutor/v1-e2e/live', '$_base/meta', '$_base/msgs']) {
    stream.emit(path, RtdbPut('/', getAt(db.root, path)));
    await t.pump();
  }
  await t.pump();
}

/// Wide window: the Known names come from the bar's Known dialog.
Future<List<String>> _known(WidgetTester t) async {
  await t.tap(glyphsLabelled('Known'));
  await t.pumpAndSettle();
  final names = [
    for (final e
        in find
            .descendant(of: find.byType(Dialog), matching: find.byType(Text))
            .evaluate())
      (e.widget as Text).data ?? '',
  ];
  await t.sendKeyEvent(LogicalKeyboardKey.escape);
  await t.pumpAndSettle();
  return names;
}

void main() {
  testWidgets('side panel concepts follow rev.catalog', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, SessionScreen(services: s), settle: false);
    await _feed(t, db, stream);
    await t.pumpAndSettle();
    expect(await _known(t), contains('• intake stroke'));
    expect(await _known(t), isNot(contains('• valve timing')));
    final concepts = [
      ...getAt(db.root, 'tutor/v1-e2e/subjects/car/concepts')! as List<Object?>,
      {'name': 'valve timing', 'at': 1},
    ];
    db.root = setAt(db.root, 'tutor/v1-e2e/subjects/car/concepts', concepts);
    stream.listens[_rev]!
      ..add(const RtdbConnected())
      ..add(RtdbPut('/', getAt(db.root, _rev)));
    await t.pumpAndSettle();
    final next = (getAt(db.root, '$_rev/catalog')! as int) + 1;
    db.root = setAt(db.root, '$_rev/catalog', next);
    stream.emit(_rev, RtdbPut('/catalog', next));
    await t.pumpAndSettle();
    expect(await _known(t), contains('• valve timing'));
  });

  testWidgets('side panel loads the subject when the session shows up', (
    t,
  ) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = services(db, stream); // nothing cached: the panel starts at "-"
    expect(await s.catalog.cached(), isEmpty);
    await pumpScreen(t, SessionScreen(services: s), settle: false);
    await _feed(t, db, stream);
    await t.pumpAndSettle();
    expect(await _known(t), contains('• intake stroke'));
    expect(find.text('-'), findsNothing);
  });
}
