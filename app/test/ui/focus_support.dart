// The FocusScreen harness shared by focus_screen_test.dart and
// focus_autostart_test.dart: a fake project status and the request readers.
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/focus_screen.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/services.dart';
import '../support/ui.dart';

const Map<String, Object> _project = {
  'id': 'hackerrank-prep',
  'name': 'HackerRank prep',
  'start': '2026-11-02',
  'end': '2026-11-05',
  'days_left': 4,
  'replaces': ['leetcode', 'reading'],
  'daily_minutes': 120,
  'unlock_minutes': 30,
  'subjects': ['automation'],
  'site_patterns': ['hackerrank.com'],
};

Map<String, Object?> _status({
  bool active = true,
  int minutes = 42,
  int? unbacked,
}) => {
  'day': '2026-11-02',
  'active': active
      ? {..._project, 'minutes': minutes, 'unbacked_minutes': ?unbacked}
      : null,
  'projects': [_project],
  'gates': [
    {'id': 'leetcode', 'label': 'LeetCode', 'replaceable': true},
    {'id': 'reading', 'label': 'Reading', 'replaceable': true},
    {'id': 'workout', 'label': 'Workout', 'replaceable': false},
  ],
  'subjects': [
    {'id': 'automation', 'title': 'Automation'},
  ],
};

late FakeRtdb _db;
late FakeStream _stream;

/// Pumps a FocusScreen and answers its status request.
Future<void> open(
  WidgetTester t, {
  bool active = true,
  bool autoStart = false,
  bool running = false,
  int minutes = 42,
  int? unbacked,
  int lastAgoMs = 60000,
}) async {
  _db = FakeRtdb();
  _stream = FakeStream();
  final kv = MemoryKv();
  if (running) {
    final last = DateTime.now().millisecondsSinceEpoch - lastAgoMs;
    await kv.set(
      'focus.timer',
      jsonEncode({'running': true, 'last': last, 'counted': 0}),
    );
  }
  final s = services(_db, _stream, kv: kv);
  addTearDown(s.focus.dispose);
  await pumpScreen(
    t,
    FocusScreen(services: s, autoStart: autoStart),
    settle: false,
  );
  await answer(
    t,
    _db,
    _stream,
    data: _status(active: active, minutes: minutes, unbacked: unbacked),
  );
}

/// How many focus_status requests the screen sent.
int statusRequests() {
  final reqs =
      getAt(_db.root, 'tutor/v1-e2e/requests') as Map<String, dynamic>?;
  return [
    for (final r in (reqs ?? {}).values)
      if (((r as Map<String, dynamic>)['req'] as Map)['kind'] == 'focus_status')
        r,
  ].length;
}

/// The bodies of the focus_event requests the screen sent.
List<Object?> focusEvents() {
  final reqs =
      getAt(_db.root, 'tutor/v1-e2e/requests') as Map<String, dynamic>?;
  return [
    for (final r in (reqs ?? {}).values)
      if (((r as Map<String, dynamic>)['req'] as Map)['kind'] == 'focus_event')
        (r['req'] as Map)['body'],
  ];
}
