/// Widget-test helpers: the fixture tree in a fake DB, a themed app around
/// one screen, and answering the relay's latest request.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/ui_zoom.dart';

import '../../tool/fixture/fixture_data.dart';
import 'fake_rtdb.dart';
import 'fake_stream.dart';
import 'services.dart';

/// Fixture "now" (ms).
final int fixtureNow = DateTime.utc(2026, 10, 12, 17).millisecondsSinceEpoch;

/// A fake DB holding the screenshot fixture under `tutor/v1`.
FakeRtdb fixtureDb() =>
    FakeRtdb()..root = setAt(null, 'tutor/v1', fixtureTree(fixtureNow));

/// Services over [db] with a primed catalog cache.
Future<TutorServices> fixtureServices(FakeRtdb db, FakeStream stream) async {
  final s = services(db, stream);
  for (final id in ['car', 'garden']) {
    await Catalog(client: db.client(), kv: s.kv).fetch(id);
  }
  return s;
}

/// Pumps [screen] in a themed app at [size].
Future<void> pumpScreen(
  WidgetTester tester,
  Widget screen, {
  Size size = const Size(1366, 900),
  bool settle = true,
}) async {
  tester.view
    ..physicalSize = size
    ..devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  // The zoom host as in TutorApp, so ⋮ -> Display size works in screens.
  await tester.pumpWidget(
    MaterialApp(
      theme: buildLightTheme(),
      builder: (context, child) => UiZoomHost(child: child!),
      home: screen,
    ),
  );
  // A screen still loading spins forever: no settling then.
  if (settle) {
    await tester.pumpAndSettle();
  } else {
    await sent(tester);
  }
}

/// The latest request written, as (rid, req).
(String, Map<String, dynamic>) lastRequest(FakeRtdb db) {
  final reqs = getAt(db.root, 'tutor/v1/requests')! as Map<String, dynamic>;
  final rid = (reqs.keys.toList()..sort()).last;
  return (
    rid,
    (reqs[rid] as Map<String, dynamic>)['req'] as Map<String, dynamic>,
  );
}

/// Answers the latest request with [data] (or an error [code] with [error]
/// and the [extra] fields the worker adds to the result node).
Future<Map<String, dynamic>> answer(
  WidgetTester tester,
  FakeRtdb db,
  FakeStream stream, {
  Map<String, Object?> data = const {},
  String? code,
  String error = 'x',
  Map<String, Object?> extra = const {},
  bool settle = true,
}) async {
  final (rid, req) = lastRequest(db);
  stream.listens['tutor/v1/requests/$rid']!.add(
    RtdbPut('/', {
      'result': code == null
          ? {'ok': true, 'at': 1, 'data': data}
          : {...extra, 'ok': false, 'at': 1, 'code': code, 'error': error},
    }),
  );
  settle ? await tester.pumpAndSettle() : await sent(tester);
  return req;
}

/// Lets a request's PUT land without waiting for the spinner to settle
/// (it animates until the result arrives, so pumpAndSettle would time out).
Future<void> sent(WidgetTester tester) async {
  for (var i = 0; i < 5; i++) {
    await tester.pump(const Duration(milliseconds: 20));
  }
}
