// Opening the live session from Home's "Continue session" button must be
// harmless (kuhy, 2026-11-22: a phone tap coincided with a `next` that
// stopped the lesson running on the PC). Opening only reads: the relay gets
// no request at all, and the only write is this install's presence record.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/services.dart';
import '../support/ui.dart';

const _root = 'tutor/v1-e2e';
const _base = '$_root/sessions/$fixtureLiveSid';

/// Every write the fake saw, as `METHOD path`.
List<String> _writes(FakeRtdb db) =>
    db.log.where((e) => !e.startsWith('GET ')).toList();

/// Opens the live session from Home as the phone does (tap the button, then
/// the screen's listens answer) and asserts nothing but presence is written.
Future<void> _openFromHome(
  WidgetTester t, {
  required bool cardDone,
  Size size = const Size(412, 915),
}) async {
  final db = fixtureDb();
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  await pumpScreen(
    t,
    HomeScreen(services: s, onSignedOut: () {}),
    size: size,
  );
  final requestsBefore = getAt(db.root, '$_root/requests');
  final liveBefore = getAt(db.root, '$_root/live');
  db.log.clear();

  await t.tap(glyphsLabelled('Continue session'));
  await t.pump();
  await t.pump(const Duration(milliseconds: 300));
  expect(find.byType(SessionScreen), findsOneWidget);

  // The listens the screen opened answer with the live session.
  for (final path in ['$_root/live', '$_base/meta', '$_base/msgs']) {
    var value = getAt(db.root, path);
    if (cardDone && path.endsWith('/meta')) {
      value = {...value! as Map<String, dynamic>, 'card_done': true};
    }
    stream.emit(path, RtdbPut('/', value));
    await t.pump();
  }
  await t.pump(const Duration(seconds: 2));
  if (cardDone) {
    // The riskiest state: Next card and Stop here are on screen, unpressed.
    expect(glyphsLabelled('Next card'), findsOneWidget);
    expect(glyphsLabelled('Stop here'), findsOneWidget);
  }

  expect(
    getAt(db.root, '$_root/requests'),
    requestsBefore,
    reason: 'opening the live session wrote a relay request',
  );
  expect(getAt(db.root, '$_root/live'), liveBefore);
  expect(
    _writes(db).where((w) => !w.contains('/presence/clients/$testDev')),
    isEmpty,
    reason: 'opening wrote more than the presence record',
  );
}

void main() {
  testWidgets('opening the live session sends no request (phone)', (t) async {
    await _openFromHome(t, cardDone: false);
  });

  testWidgets('opening a live session at Card done presses nothing', (t) async {
    await _openFromHome(t, cardDone: true);
  });
}
