// DOCS-contract-struggle.md §1/§4: Review shows the card's mnemonic under
// the back, and right after a rating that leaves struggle at 3, 6, ... a
// dismissable "Struggling with this card?" offer; "Get help" sends
// `session_start` `struggle: true` and opens the session; greyed out while
// the PC is offline. Dismissing records nothing.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/review_screen.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/ui.dart';

const _cardPath = 'tutor/v1/subjects/car/cards/eng-crank';
const _mnemonic = 'Crank: up-down in, round and round out';
const _offer = 'Struggling with this card?';
const _day = 86400000;
final _then = DateTime.fromMillisecondsSinceEpoch(fixtureNow);

/// eng-crank taught a month ago (with a mnemonic), then [misses] Again ratings
/// at its current rev.
Future<(FakeRtdb, FakeStream, TutorServices)> _setUp(int misses) async {
  final db = fixtureDb();
  db.root = setAt(db.root, '$_cardPath/mnemonic', _mnemonic);
  final rev = (getAt(db.root, '$_cardPath/rev')! as num).toInt();
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  final at = fixtureNow - 30 * _day;
  await s.events.record(TaughtEvent(subject: 'car', card: 'eng-crank', at: at));
  for (var i = 1; i <= misses; i++) {
    await s.events.record(
      ReviewEvent(
        subject: 'car',
        card: 'eng-crank',
        at: at + i * _day,
        grade: Grade.again,
        rev: rev,
      ),
    );
  }
  return (db, stream, s);
}

Future<void> _rate(WidgetTester t, String grade) async {
  await t.sendKeyEvent(LogicalKeyboardKey.space);
  await t.pumpAndSettle();
  await t.tap(find.text(grade));
  await t.pumpAndSettle();
}

void main() {
  testWidgets('mnemonic under the back; offer at 3; dismiss records nothing', (
    t,
  ) async {
    final (_, _, s) = await _setUp(2);
    await pumpScreen(t, ReviewScreen(services: s, now: () => _then));
    expect(find.text(_mnemonic), findsNothing); // the front only
    await t.sendKeyEvent(LogicalKeyboardKey.space);
    await t.pumpAndSettle();
    expect(find.text(_mnemonic), findsOneWidget);
    expect(find.text(_offer), findsNothing);
    await t.tap(find.text('1 Again'));
    await t.pumpAndSettle();
    expect(find.text('All done'), findsOneWidget); // never blocks the queue
    expect(find.text(_offer), findsOneWidget);
    expect(find.textContaining('What does the crankshaft do?'), findsWidgets);
    final logged = (await s.events.all()).length;

    await t.tap(find.text('Back'));
    await t.pumpAndSettle();
    expect(find.text(_offer), findsNothing); // the Again is undone
    await t.tap(find.text('1 Again'));
    await t.pumpAndSettle();
    expect(find.text(_offer), findsOneWidget);
    await t.tap(find.text('Dismiss'));
    await t.pumpAndSettle();
    expect(find.text(_offer), findsNothing);
    // Back's undo and the new Again; the dismissal itself writes nothing.
    expect((await s.events.all()).length, logged + 2);
  });

  testWidgets('module review: 3 Again ratings in one run; Good never offers', (
    t,
  ) async {
    final (_, _, s) = await _setUp(0);
    await pumpScreen(
      t,
      ReviewScreen(
        services: s,
        module: const ModuleRef(subject: 'car', module: 'engine', title: 'E'),
        now: () => _then,
      ),
    );
    await _rate(t, '1 Again');
    await _rate(t, '1 Again');
    expect(find.text(_offer), findsNothing);
    await _rate(t, '1 Again');
    expect(find.text(_offer), findsOneWidget);
    await _rate(t, '3 Good'); // the next rating replaces the offer
    expect(find.text(_offer), findsNothing);
  });

  testWidgets('Get help: session_start struggle, then the session', (t) async {
    final (db, stream, s) = await _setUp(2);
    await pumpScreen(t, ReviewScreen(services: s, now: () => _then));
    await _rate(t, '1 Again');
    await t.tap(find.text('Get help'));
    await sent(t);
    final req = await answer(t, db, stream, settle: false);
    expect(req['kind'], 'session_start');
    final body = req['body'] as Map<String, dynamic>;
    expect(body['subject'], 'car');
    expect(body['card'], 'eng-crank');
    expect(body['struggle'], isTrue);
    await sent(t);
    expect(find.byType(SessionScreen), findsOneWidget);
  });

  testWidgets('PC offline: Get help greyed out', (t) async {
    final (_, _, s) = await _setUp(2);
    await pumpScreen(t, ReviewScreen(services: s, now: () => _then));
    s.presence.state.value = PcPresence.offline;
    await _rate(t, '1 Again');
    expect(find.text('Get help'), findsNothing);
    final button = t.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'PC offline'),
    );
    expect(button.onPressed, isNull);
    s.presence.state.value = PcPresence.online;
    await t.pumpAndSettle();
    expect(find.text('Get help'), findsOneWidget);
  });
}
