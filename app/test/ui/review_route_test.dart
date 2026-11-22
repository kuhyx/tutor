// `/review/<subject>/<module>`, the lock's "review this module": opens that
// module's review (`openReview(module:)`), on a cold start and by hand-over
// to an open window; a module with nothing to review, or not in the plan,
// shows the subject's plan instead, an unknown subject stays where it is.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/ui/deep_link.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/plan_screen.dart';
import 'package:tutor/ui/review_screen.dart';
import 'package:tutor/ui/route_inbox.dart';
import 'package:tutor/ui/session/session_screen.dart';
import 'package:tutor/util/ulid.dart';

import '../support/fake_stream.dart';
import '../support/learn_finders.dart';
import '../support/ui.dart';

/// The PC worker's device id: it writes `taught` (curriculum §4).
const _pcDev = '7c1e9a52-3b4d-4f60-8a1b-2c3d4e5f6a70';

/// The fixture's `car` with [cards] taught just now, as the worker does.
Future<TutorServices> _taught(List<String> cards) async {
  final s = await fixtureServices(fixtureDb(), FakeStream());
  final pc = EventLog(
    client: s.client,
    kv: MemoryKv(),
    dev: _pcDev,
    ulid: UlidGenerator(),
  );
  for (final c in cards) {
    await pc.record(TaughtEvent(subject: 'car', card: c, at: fixtureNow));
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

void main() {
  test('an open window takes /review offers; /learn still, others not', () {
    expect(handedOffer('learn /review/car/fuel'), isTrue);
    expect(handedOffer('learn /learn/car/fuel'), isTrue);
    expect(handedOffer('learn /rework/s/m/x'), isTrue);
    expect(handedOffer('learn /review'), isFalse);
    expect(handedOffer('learn /focus'), isFalse);
    expect(handedOffer('took /review/car/fuel'), isFalse);
  });

  testWidgets('the route opens the module review, not the due queue', (
    t,
  ) async {
    final s = await _taught(['fuel-spark', 'eng-strokes']);
    final ctx = await _root(t);
    unawaited(openRoute(ctx, s, '/review/car/fuel'));
    await t.pumpAndSettle();
    final screen = t.widget<ReviewScreen>(find.byType(ReviewScreen));
    expect((screen.module?.subject, screen.module?.module), ('car', 'fuel'));
    expect(screen.module?.title, 'Fuel and ignition');
    expect(find.text('What ignites the mixture?'), findsOneWidget);
    expect(spoken('1 left'), findsOneWidget);
    expect(find.byType(PlanScreen), findsNothing);
  });

  testWidgets('cold start: Home opens the module review', (t) async {
    final s = await _taught(['fuel-spark']);
    await pumpScreen(
      t,
      HomeScreen(
        services: s,
        onSignedOut: () {},
        initialRoute: '/review/car/fuel',
      ),
    );
    await t.pumpAndSettle();
    final screen = t.widget<ReviewScreen>(find.byType(ReviewScreen));
    expect(screen.module?.module, 'fuel');
    expect(find.text('What ignites the mixture?'), findsOneWidget);
  });

  testWidgets('hand-over: an open window opens it over its screen', (t) async {
    final s = await _taught(['fuel-spark']);
    final routes = StreamController<String>.broadcast();
    await pumpScreen(
      t,
      RouteInbox(services: s, routes: routes.stream, child: const Text('x')),
    );
    routes.add('/review/car/fuel');
    await t.pumpAndSettle();
    expect(
      t.widget<ReviewScreen>(find.byType(ReviewScreen)).module?.module,
      'fuel',
    );
    await t.pumpWidget(const SizedBox());
    await routes.close();
  });

  for (final (name, taught, module) in [
    ('nothing taught', <String>[], 'fuel'),
    ('a module outside the plan', <String>['fuel-spark'], 'nope'),
    ('a module without cards', <String>['fuel-spark'], 'drivetrain'),
  ]) {
    testWidgets('$name: the subject plan, no review, no session', (t) async {
      final s = await _taught(taught);
      final ctx = await _root(t);
      unawaited(openRoute(ctx, s, '/review/car/$module'));
      await t.pumpAndSettle();
      expect(t.widget<PlanScreen>(find.byType(PlanScreen)).subject, 'car');
      expect(find.byType(ReviewScreen), findsNothing);
      expect(find.byType(SessionScreen), findsNothing);
    });
  }

  testWidgets('a module already passed: the plan as well', (t) async {
    final s = await _taught(['fuel-spark']);
    await s.events.record(
      ReviewEvent(
        subject: 'car',
        card: 'fuel-spark',
        grade: Grade.good,
        rev: 1,
        at: fixtureNow,
      ),
    );
    final ctx = await _root(t);
    unawaited(openRoute(ctx, s, '/review/car/fuel'));
    await t.pumpAndSettle();
    expect(find.byType(PlanScreen), findsOneWidget);
    expect(find.byType(ReviewScreen), findsNothing);
  });

  testWidgets('an unknown subject stays on the page', (t) async {
    final s = await _taught(['fuel-spark']);
    final ctx = await _root(t);
    unawaited(openRoute(ctx, s, '/review/nope/fuel'));
    await t.pumpAndSettle();
    expect(find.byType(PlanScreen), findsNothing);
    expect(find.byType(ReviewScreen), findsNothing);
  });

  testWidgets('/review alone is still the due queue of every subject', (
    t,
  ) async {
    final s = await _taught(['fuel-spark']);
    final ctx = await _root(t);
    unawaited(openRoute(ctx, s, '/review'));
    await t.pumpAndSettle();
    final screen = t.widget<ReviewScreen>(find.byType(ReviewScreen));
    expect((screen.module, screen.subject), (null, null));
  });
}
