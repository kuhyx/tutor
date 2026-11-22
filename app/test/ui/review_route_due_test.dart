// `/review/<subject>/<module>` shows the module's cards in the due queue now:
// the cards the signed review_due.json counts as due
// (DOCS-contract-review-due.md). The rest of the route is review_route_test.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/plan_screen.dart';
import 'package:tutor/ui/review_screen.dart';
import 'package:tutor/util/ulid.dart';

import '../support/fake_stream.dart';
import '../support/learn_finders.dart';
import '../support/ui.dart';

/// The PC worker's device id: it writes `taught` (curriculum §4).
const _pcDev = '7c1e9a52-3b4d-4f60-8a1b-2c3d4e5f6a70';

/// The fixture's `car` with each card of [cards] taught at its time (ms), on
/// a db where [suspended] cards are suspended.
Future<TutorServices> _taughtAt(
  Map<String, int> cards, {
  List<String> suspended = const [],
}) async {
  final db = fixtureDb();
  for (final c in suspended) {
    db.root = setAt(
      db.root,
      'tutor/v1-e2e/subjects/car/cards/$c/suspended',
      true,
    );
  }
  final s = await fixtureServices(db, FakeStream());
  final pc = EventLog(
    client: s.client,
    kv: MemoryKv(),
    dev: _pcDev,
    ulid: UlidGenerator(),
  );
  for (final MapEntry(key: c, value: at) in cards.entries) {
    await pc.record(TaughtEvent(subject: 'car', card: c, at: at));
  }
  await pc.flush();
  await s.events.pull();
  return s;
}

Future<BuildContext> _root(WidgetTester t) async {
  late BuildContext ctx;
  await pumpScreen(
    t,
    Builder(
      builder: (context) {
        ctx = context;
        return const SizedBox();
      },
    ),
  );
  return ctx;
}

// The engine module has eng-strokes, eng-crank, eng-valves, in that order.
const _day = 86400000;
final int _longAgo = fixtureNow - 365 * _day;
final int _justNow = DateTime.now().millisecondsSinceEpoch;

void main() {
  testWidgets('a card passed earlier and due again is shown', (t) async {
    final s = await _taughtAt({
      'eng-strokes': _longAgo,
      'eng-crank': _longAgo,
      'eng-valves': _longAgo,
    });
    await s.events.record(
      ReviewEvent(
        subject: 'car',
        card: 'eng-strokes',
        grade: Grade.good,
        rev: 1,
        at: _longAgo + _day,
      ),
    );
    final ctx = await _root(t);
    unawaited(openRoute(ctx, s, '/review/car/engine'));
    await t.pumpAndSettle();
    expect(find.byType(ReviewScreen), findsOneWidget);
    expect(find.byType(PlanScreen), findsNothing);
    expect(spoken('3 left'), findsOneWidget);
    expect(find.text('What are the four strokes?'), findsOneWidget);
  });

  testWidgets('a taught, never passed card due later is not shown', (t) async {
    final s = await _taughtAt({
      'eng-strokes': _longAgo,
      'eng-crank': _justNow,
      'eng-valves': _justNow,
    });
    final ctx = await _root(t);
    unawaited(openRoute(ctx, s, '/review/car/engine'));
    await t.pumpAndSettle();
    expect(find.byType(ReviewScreen), findsOneWidget);
    expect(spoken('1 left'), findsOneWidget);
    expect(find.text('What are the four strokes?'), findsOneWidget);
  });

  testWidgets('only cards due later: the subject plan', (t) async {
    final s = await _taughtAt({'eng-strokes': _justNow, 'eng-crank': _justNow});
    final ctx = await _root(t);
    unawaited(openRoute(ctx, s, '/review/car/engine'));
    await t.pumpAndSettle();
    expect(t.widget<PlanScreen>(find.byType(PlanScreen)).subject, 'car');
    expect(find.byType(ReviewScreen), findsNothing);
  });

  testWidgets('flagged and suspended due cards are not shown', (t) async {
    final s = await _taughtAt(
      {'eng-strokes': _longAgo, 'eng-crank': _longAgo, 'eng-valves': _longAgo},
      suspended: ['eng-valves'],
    );
    await s.events.record(
      FlagEvent(
        subject: 'car',
        card: 'eng-crank',
        rev: 1,
        reason: 'wrong',
        at: _longAgo + _day,
      ),
    );
    final ctx = await _root(t);
    unawaited(openRoute(ctx, s, '/review/car/engine'));
    await t.pumpAndSettle();
    expect(spoken('1 left'), findsOneWidget);
    expect(find.text('What are the four strokes?'), findsOneWidget);
  });

  testWidgets('only flagged or suspended due cards: the plan', (t) async {
    final s = await _taughtAt(
      {'eng-strokes': _longAgo, 'eng-valves': _longAgo},
      suspended: ['eng-valves'],
    );
    await s.events.record(
      FlagEvent(
        subject: 'car',
        card: 'eng-strokes',
        rev: 1,
        reason: 'wrong',
        at: _longAgo + _day,
      ),
    );
    final ctx = await _root(t);
    unawaited(openRoute(ctx, s, '/review/car/engine'));
    await t.pumpAndSettle();
    expect(find.byType(PlanScreen), findsOneWidget);
    expect(find.byType(ReviewScreen), findsNothing);
  });

  testWidgets('Again comes back; the run ends on Good', (t) async {
    final s = await _taughtAt({'eng-strokes': _longAgo});
    final ctx = await _root(t);
    unawaited(openRoute(ctx, s, '/review/car/engine'));
    await t.pumpAndSettle();
    for (final grade in ['1 Again', '3 Good']) {
      await t.tap(spoken('Show answer (Space)'));
      await t.pumpAndSettle();
      await t.tap(spoken(grade));
      await t.pumpAndSettle();
    }
    expect(spokenHas('All done'), findsOneWidget);
  });

  testWidgets('a module passed and not due again: the plan', (t) async {
    final s = await _taughtAt({'fuel-spark': _justNow});
    await s.events.record(
      ReviewEvent(
        subject: 'car',
        card: 'fuel-spark',
        grade: Grade.good,
        rev: 1,
        at: _justNow,
      ),
    );
    final ctx = await _root(t);
    unawaited(openRoute(ctx, s, '/review/car/fuel'));
    await t.pumpAndSettle();
    expect(find.byType(PlanScreen), findsOneWidget);
    expect(find.byType(ReviewScreen), findsNothing);
  });
}
