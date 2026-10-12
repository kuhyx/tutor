import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/editor_screen.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/plan_screen.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/ui.dart';

const _rev = 'tutor/v1/rev';
const _car = 'tutor/v1/subjects/car';
const _garden = 'tutor/v1/subjects/garden';

/// The rev listen's connect snapshot (the watcher's baseline).
void _connect(FakeRtdb db, FakeStream stream) => stream.listens[_rev]!
  ..add(const RtdbConnected())
  ..add(RtdbPut('/', getAt(db.root, _rev)));

/// The worker bumps `rev.catalog` after changing the db.
Future<void> _bump(WidgetTester t, FakeRtdb db, FakeStream stream) async {
  final next = (getAt(db.root, '$_rev/catalog')! as int) + 1;
  db.root = setAt(db.root, '$_rev/catalog', next);
  stream.listens[_rev]!.add(RtdbPut('/catalog', next));
  await t.pumpAndSettle();
}

/// Patches module [i] of [subject]'s plan (json_tree only walks maps).
void _module(FakeRtdb db, String subject, int i, Map<String, Object> patch) {
  final path = '$subject/plan/modules';
  final modules = [...getAt(db.root, path)! as List<Object?>];
  modules[i] = {...modules[i]! as Map<String, dynamic>, ...patch};
  db.root = setAt(db.root, path, modules);
}

int _gets(FakeRtdb db, String path) =>
    db.log.where((l) => l == 'GET /$path').length;

void main() {
  testWidgets('Plan updates by itself as a module generates', (t) async {
    final db = fixtureDb();
    _module(db, _car, 2, {'status': 'generating'});
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, PlanScreen(services: s, subject: 'car'));
    expect(find.textContaining('generating'), findsOneWidget);
    _connect(db, stream);
    // A stats bump and a same-value reconnect snapshot fetch nothing.
    stream.listens[_rev]!
      ..add(const RtdbPut('/stats', 9))
      ..add(const RtdbConnected())
      ..add(RtdbPut('/', getAt(db.root, _rev)));
    await t.pumpAndSettle();
    expect(_gets(db, _car), 2); // primed cache + first load
    _module(db, _car, 2, {'status': 'ready'});
    _module(db, _car, 2, {'cards': 3});
    final next = (getAt(db.root, '$_rev/catalog')! as int) + 1;
    db.root = setAt(db.root, '$_rev/catalog', next);
    stream.listens[_rev]!.add(RtdbPut('/catalog', next));
    await t.pump();
    // The old plan stays on screen while the refetch runs: no spinner.
    expect(find.byType(CircularProgressIndicator), findsNothing);
    await t.pumpAndSettle();
    expect(find.textContaining('ready · 3 cards'), findsNWidgets(2));
    expect(find.textContaining('generating'), findsNothing);
    // A failed refetch keeps the plan and says so.
    db.offline = true;
    await _bump(t, db, stream);
    expect(find.textContaining('Could not refresh'), findsOneWidget);
    expect(find.text('The four-stroke engine'), findsOneWidget);
  });

  testWidgets('draft: clean editor follows; dirty one gets a banner', (
    t,
  ) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      PlanScreen(services: s, subject: 'garden'),
      size: const Size(1000, 2400),
    );
    _connect(db, stream);
    // Same plan rev, new title, no local edits: replaced in place.
    _module(db, _garden, 0, {'title': 'Sunlight'});
    await _bump(t, db, stream);
    expect(find.text('1. Sunlight'), findsOneWidget);
    expect(find.text('Undo edits'), findsNothing);

    // Local edits + a redrafted plan: the edits stay, a banner offers it.
    await t.tap(find.byTooltip('Move down').first);
    await t.pumpAndSettle();
    db.root = setAt(db.root, '$_garden/plan/rev', 2);
    _module(db, _garden, 1, {'title': 'Pots'});
    await _bump(t, db, stream);
    expect(find.text('Plan changed — reload'), findsOneWidget);
    expect(find.text('1. Soil and containers'), findsOneWidget);
    await t.tap(find.text('Reload plan'));
    await t.pumpAndSettle();
    expect(find.text('Plan changed — reload'), findsNothing);
    expect(find.text('1. Sunlight'), findsOneWidget);
    expect(find.text('2. Pots'), findsOneWidget);
    expect(find.text('Undo edits'), findsNothing);

    // Edits undone while a change waits: it lands at once.
    await t.tap(find.byTooltip('Move down').first);
    await t.pumpAndSettle();
    db.root = setAt(db.root, '$_garden/plan/rev', 3);
    _module(db, _garden, 2, {'title': 'Rain'});
    await _bump(t, db, stream);
    expect(find.text('Plan changed — reload'), findsOneWidget);
    await t.tap(find.text('Undo edits'));
    await t.pumpAndSettle();
    expect(find.text('Plan changed — reload'), findsNothing);
    expect(find.text('3. Rain'), findsOneWidget);

    // A bump that leaves this plan as it is never raises the banner.
    await t.tap(find.byTooltip('Move down').first);
    await t.pumpAndSettle();
    await _bump(t, db, stream);
    expect(find.text('Plan changed — reload'), findsNothing);
    expect(find.text('Undo edits'), findsOneWidget);
  });

  testWidgets('own Save: the bump before its result raises no banner', (
    t,
  ) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      PlanScreen(services: s, subject: 'garden'),
      size: const Size(1000, 2400),
    );
    _connect(db, stream);
    await t.tap(find.byTooltip('Move down').first);
    await t.pumpAndSettle();
    await t.tap(find.text('Save edits'));
    await sent(t);
    // The worker applied the edit and bumped rev before the result came.
    final saved = getAt(db.root, '$_garden/plan/modules')! as List<Object?>;
    db.root = setAt(db.root, '$_garden/plan/modules', [
      saved[1],
      saved[0],
      ...saved.skip(2),
    ]);
    db.root = setAt(db.root, '$_garden/plan/rev', 2);
    final next = (getAt(db.root, '$_rev/catalog')! as int) + 1;
    db.root = setAt(db.root, '$_rev/catalog', next);
    stream.listens[_rev]!.add(RtdbPut('/catalog', next));
    await sent(t);
    expect(find.text('Plan changed — reload'), findsNothing);
    await answer(t, db, stream, data: {'plan_rev': 2});
    expect(find.text('Plan changed — reload'), findsNothing);
    expect(find.text('1. Soil and containers'), findsOneWidget);
    expect(find.text('Undo edits'), findsNothing);
  });

  testWidgets('Home refreshes in place, but not while under Plan', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      HomeScreen(services: s, onSignedOut: () {}),
      size: const Size(412, 1400),
    );
    _connect(db, stream);
    db.root = setAt(db.root, '$_garden/meta/title', 'Balcony vegetables');
    await _bump(t, db, stream);
    expect(find.text('Balcony vegetables'), findsOneWidget);

    await t.tap(find.text('Balcony vegetables'));
    await t.pumpAndSettle();
    expect(stream.listens[_rev]!.hasListener, isTrue); // one shared listen
    final homeLoads = _gets(db, 'tutor/v1/meta');
    db.root = setAt(db.root, '$_garden/meta/title', 'Herbs');
    await _bump(t, db, stream);
    expect(_gets(db, 'tutor/v1/meta'), homeLoads);
    await t.pageBack();
    await t.pumpAndSettle();
    expect(find.text('Herbs'), findsOneWidget); // refreshed on return
  });

  testWidgets('Editor shows new cards as they land', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      EditorScreen(services: s, subject: 'car'),
      size: const Size(800, 1600),
    );
    expect(find.text('1 card · ready'), findsOneWidget);
    _connect(db, stream);
    db.root = setAt(db.root, '$_car/cards/fuel-mix', {
      ...getAt(db.root, '$_car/cards/fuel-spark')! as Map<String, dynamic>,
      'order': 2,
    });
    await _bump(t, db, stream);
    expect(find.text('2 cards · ready'), findsOneWidget);
    db.offline = true;
    await _bump(t, db, stream); // a failed refresh keeps the list
    expect(find.text('2 cards · ready'), findsOneWidget);
  });
}
