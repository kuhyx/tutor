// C4: `/learn/<subject>/<module>` (the LeetCode lock's learn button) and the
// plan screen's lock glyph on modules the guard does not let the tutor teach.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/deep_link.dart';
import 'package:tutor/ui/learn_bits.dart';
import 'package:tutor/ui/module_tile.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/plan_grid.dart';
import 'package:tutor/ui/plan_screen.dart';
import 'package:tutor/ui/session/blocked_panel.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/ui.dart';

/// A root to open routes from; returns its context.
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

Future<void> _frames(WidgetTester t) async {
  for (var i = 0; i < 10; i++) {
    await t.pump(const Duration(milliseconds: 50));
  }
}

Object? _requests(FakeRtdb db) => getAt(db.root, 'tutor/v1-e2e/requests');

Module _module({bool? teachable}) => Module.fromJson({
  'id': 'fuel',
  'title': 'Fuel and ignition',
  'status': 'ready',
  'cards': 3,
  'teachable': ?teachable,
});

void main() {
  test('a missing teachable key means teachable; plan_edit never sends it', () {
    expect(_module().teachable, isTrue);
    expect(_module(teachable: true).teachable, isTrue);
    expect(_module(teachable: false).teachable, isFalse);
    expect(
      _module(teachable: false).toJson().containsKey('teachable'),
      isFalse,
    );
  });

  test('joining the windows is safe off the web', () {
    joinWindows(claim: true);
    joinWindows(claim: false);
  });

  for (final (teachable, glyphs) in [(false, 1), (true, 0), (null, 0)]) {
    testWidgets('the lock glyph: teachable $teachable', (t) async {
      await pumpScreen(
        t,
        Scaffold(
          body: ModuleProgressTile(
            module: _module(teachable: teachable),
            onRetry: () {},
          ),
        ),
      );
      expect(find.byType(TeachLock), findsNWidgets(glyphs));
      await pumpScreen(
        t,
        Scaffold(
          body: PlanFit(
            header: const [],
            plan: Plan(
              rev: 1,
              status: 'approved',
              modules: [_module(teachable: teachable)],
            ),
            progress: null,
            onRetry: () {},
            onReview: (_) {},
          ),
        ),
        size: const Size(400, 800),
      );
      expect(find.byType(TeachLock), findsNWidgets(glyphs));
    });
  }

  testWidgets('the route starts a session on the module and stays on it', (
    t,
  ) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    final ctx = await _root(t);
    unawaited(openRoute(ctx, s, '/learn/car/fuel'));
    await _frames(t);
    expect(find.byType(SessionScreen), findsOneWidget);
    final (_, req) = lastRequest(db);
    expect(req['kind'], 'session_start');
    final body = req['body'] as Map;
    expect(
      (body['subject'], body['module'], body['card']),
      ('car', 'fuel', null),
    );
    await answer(
      t,
      db,
      stream,
      data: {'session': '20261122-090000-c4c4'},
      settle: false,
    );
    await _frames(t);
    expect(find.byType(SessionScreen), findsOneWidget);
    expect(find.byType(PlanScreen), findsNothing);
  });

  for (final code in [
    'no_card_left',
    'locked',
    'unknown_card',
    'bad_request',
  ]) {
    testWidgets('refused ($code): the subject plan instead, no panel', (
      t,
    ) async {
      final db = fixtureDb();
      final stream = FakeStream();
      final s = await fixtureServices(db, stream);
      final ctx = await _root(t);
      unawaited(openRoute(ctx, s, '/learn/car/drivetrain'));
      await _frames(t);
      await answer(
        t,
        db,
        stream,
        code: code,
        extra: {'subject_id': 'car'},
        settle: false,
      );
      expect(find.byType(BlockedPanel), findsNothing);
      await _frames(t);
      expect(find.byType(SessionScreen), findsNothing);
      expect(t.widget<PlanScreen>(find.byType(PlanScreen)).subject, 'car');
    });
  }

  testWidgets('an unknown subject stays home and sends nothing', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    final ctx = await _root(t);
    for (final route in [
      '/learn/nope/a',
      '/learn/Not A Slug/a',
      '/learn/car',
    ]) {
      unawaited(openRoute(ctx, s, route));
      await _frames(t);
      expect(find.byType(SessionScreen), findsNothing, reason: route);
      expect(find.byType(PlanScreen), findsNothing, reason: route);
    }
    expect(_requests(db), isNull);
  });
}
