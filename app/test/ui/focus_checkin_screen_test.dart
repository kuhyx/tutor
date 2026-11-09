import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/focus_screen.dart';

import '../model/samples.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/services.dart';
import '../support/ui.dart';

const Map<String, Object> _project = {
  'id': 'prep',
  'name': 'Prep',
  'start': '2026-11-02',
  'end': '2026-11-05',
  'days_left': 4,
  'replaces': ['leetcode'],
  'daily_minutes': 60,
  'unlock_minutes': 10,
  'subjects': ['car'],
  'site_patterns': <String>[],
};

Map<String, Object?> _status({List<String> subjects = const ['car']}) => {
  'day': '2026-11-02',
  'active': {..._project, 'subjects': subjects, 'minutes': 5},
  'projects': [_project],
  'gates': <Object>[],
  'subjects': <Object>[],
};

void main() {
  late FakeRtdb db;
  late FakeStream stream;
  late TutorServices svc;

  // A run whose check-in is due (7.5 min since the last tap), with one
  // taught card of `car` and the project's status cached, as on a device
  // that opened the Focus screen before.
  Future<void> open(WidgetTester t, {List<String> subjects = const ['car']}) {
    db = FakeRtdb();
    stream = FakeStream();
    final kv = MemoryKv();
    return t
        .runAsync(() async {
          final now = DateTime.now().millisecondsSinceEpoch;
          await kv.set(
            'focus.timer',
            jsonEncode({'running': true, 'last': now - 450000, 'counted': 0}),
          );
          await kv.set('focus.status', jsonEncode(_status(subjects: subjects)));
          await kv.set(
            kCatalogCacheKey,
            jsonEncode({
              'rev': 1,
              'subjects': {
                'car': {
                  'meta': subjectMeta,
                  'cards': {
                    'a': {...card, 'front': 'What is a rung?'},
                  },
                },
              },
            }),
          );
          final s = svc = services(db, stream, kv: kv);
          await s.events.record(
            TaughtEvent(subject: 'car', card: 'a', at: now - 86400000),
          );
          await pumpScreen(t, FocusScreen(services: s), settle: false);
        })
        .then((_) async {
          await answer(
            t,
            db,
            stream,
            data: _status(subjects: subjects),
            settle: false,
          );
          await t.runAsync(() => Future<void>.delayed(Duration.zero));
          await t.pump();
        });
  }

  // The timer was loaded in real async (runAsync), so its futures need the
  // real event loop as well as fake-time pumps.
  Future<void> settle(WidgetTester t) async {
    for (var i = 0; i < 3; i++) {
      await t.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 20)),
      );
      await t.pump(const Duration(milliseconds: 20));
    }
  }

  // A live run ticks: stop the ticker before the test ends.
  Future<void> done(WidgetTester t) async {
    svc.focus.dispose();
    await t.pumpWidget(const SizedBox());
  }

  List<Map<String, dynamic>> focusEvents() {
    final reqs = getAt(db.root, 'tutor/v1/requests') as Map<String, dynamic>?;
    return [
      for (final r in (reqs ?? {}).values)
        if (((r as Map<String, dynamic>)['req'] as Map)['kind'] ==
            'focus_event')
          ((r['req'] as Map)['body'] as Map).cast<String, dynamic>(),
    ];
  }

  List<Map<String, dynamic>> reviews() {
    final log = getAt(db.root, 'tutor/v1/log/$testDev') as Map?;
    return [
      for (final e in (log ?? {}).values)
        if ((e as Map)['k'] == 'review') e.cast<String, dynamic>(),
    ];
  }

  testWidgets('the due check-in is a card inline, not the tap', (t) async {
    await open(t);
    expect(find.text('What is a rung?'), findsOneWidget);
    expect(find.text('Still working'), findsNothing);
    expect(find.text('Show answer (Space)'), findsOneWidget);
    await done(t);
  });

  testWidgets('rating it (after 1 s) is a review and a card beat', (t) async {
    await open(t);
    await t.tap(find.text('Show answer (Space)'));
    await t.pump();
    await t.runAsync(() => Future<void>.delayed(const Duration(seconds: 1)));
    await t.tap(find.text('1 Again'));
    await settle(t);
    expect(find.text('What is a rung?'), findsNothing);
    final review = reviews().single;
    expect((review['src'], review['r']), ('checkin', 1));
    final beat = focusEvents().single;
    expect(
      (beat['event'], beat['subject'], beat['card']),
      ('card', 'car', 'a'),
    );
    expect(beat['ts'], review['at']);
    await done(t);
  });

  testWidgets('a rating under 1 s is graded, but no beat', (t) async {
    await open(t);
    await t.tap(find.text('Show answer (Space)'));
    await t.pump();
    await t.tap(find.text('3 Good'));
    await settle(t);
    expect(reviews(), hasLength(1));
    expect(focusEvents(), isEmpty);
    await done(t);
  });

  testWidgets('no subjects: the old Still working tap sends checkin', (
    t,
  ) async {
    await open(t, subjects: const []);
    expect(find.text('Still working'), findsOneWidget);
    await t.tap(find.text('Still working'));
    await settle(t);
    expect(focusEvents().single['event'], 'checkin');
    await done(t);
  });
}
