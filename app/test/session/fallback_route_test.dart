// The outage chooser (plan e79be0be-0 step 2): due -> Review, else an
// untaught card (the `read_next` probe) -> read mode, else a taught card ->
// the drill, else read mode's empty glyph; always in the scope given.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/model/codes.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/model/outage_window.dart';
import 'package:tutor/session/fallback_route.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/read.dart';
import '../support/ui.dart';

final int _month = DateTime.now().millisecondsSinceEpoch - 30 * 86400000;

Future<(FakeRtdb, FakeStream, TutorServices)> _setUp() async {
  final db = fixtureDb();
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  return (db, stream, s);
}

/// Runs [decideFallback] from a tap, as Home does; the result lands in
/// the returned holder once the probe is answered.
Future<List<FallbackRoute>> _decide(
  WidgetTester t,
  TutorServices s, {
  String? subject,
}) async {
  final out = <FallbackRoute>[];
  await pumpScreen(
    t,
    Builder(
      builder: (context) => IconButton(
        icon: const Icon(Icons.play_arrow),
        onPressed: () async =>
            out.add(await decideFallback(s, subject: subject)),
      ),
    ),
  );
  await t.tap(find.byType(IconButton));
  await sent(t);
  return out;
}

void main() {
  test('the order: due, then readable, then taught, then empty', () {
    FallbackRoute pick(int due, {required bool read, required bool taught}) =>
        chooseFallback(due: due, readable: read, taught: taught);
    expect(pick(1, read: true, taught: true), FallbackRoute.review);
    expect(pick(0, read: true, taught: true), FallbackRoute.read);
    expect(pick(0, read: false, taught: true), FallbackRoute.drill);
    expect(pick(0, read: false, taught: false), FallbackRoute.empty);
  });

  test('an outage window becomes the drill and read mode value', () {
    const w = OutageWindow(until: 99, reason: UnavailableReason.overloaded);
    final u = unavailableOf(w);
    expect((u.until, u.reason), (99, 'overloaded'));
  });

  testWidgets('due cards: Review, and no request goes out', (t) async {
    final (db, _, s) = await _setUp();
    await s.events.record(
      TaughtEvent(subject: 'car', card: 'eng-crank', at: _month),
    );
    final out = await _decide(t, s, subject: 'car');
    await t.pumpAndSettle();
    expect(out, [FallbackRoute.review]);
    expect(db.root.toString().contains('read_next'), isFalse);
  });

  testWidgets('due cards of another subject do not count', (t) async {
    final (db, stream, s) = await _setUp();
    await s.events.record(
      TaughtEvent(subject: 'car', card: 'eng-crank', at: _month),
    );
    final route = await _decide(t, s, subject: 'garden');
    final req = await answer(t, db, stream, data: readCard());
    expect(req['kind'], 'read_next');
    expect(req['body'], {'subject': 'garden'});
    expect(route, [FallbackRoute.read]);
  });

  testWidgets('nothing to read but a taught card: the drill', (t) async {
    final (db, stream, s) = await _setUp();
    final now = DateTime.now().millisecondsSinceEpoch;
    await s.events.record(
      TaughtEvent(subject: 'car', card: 'eng-crank', at: now),
    );
    final route = await _decide(t, s);
    final req = await answer(t, db, stream, data: {'empty': true});
    expect(req['body'], {'subject': null});
    expect(route, [FallbackRoute.drill]);
  });

  testWidgets('a taught card elsewhere is no drill for this subject', (
    t,
  ) async {
    final (db, stream, s) = await _setUp();
    final now = DateTime.now().millisecondsSinceEpoch;
    await s.events.record(
      TaughtEvent(subject: 'car', card: 'eng-crank', at: now),
    );
    final route = await _decide(t, s, subject: 'garden');
    await answer(t, db, stream, data: {'empty': true});
    expect(route, [FallbackRoute.empty]);
  });

  testWidgets('a failed probe still opens read mode (it says why)', (t) async {
    final (db, stream, s) = await _setUp();
    final route = await _decide(t, s);
    await answer(t, db, stream, code: 'worker_error');
    expect(route, [FallbackRoute.read]);
  });

  testWidgets('an unreadable probe reply still opens read mode', (t) async {
    final (db, stream, s) = await _setUp();
    final route = await _decide(t, s);
    await answer(t, db, stream, data: {'card': 'x'});
    expect(route, [FallbackRoute.read]);
  });
}
