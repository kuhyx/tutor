// Phone (narrow) Home, Plan and Progress: tiles keep their tap action and
// every former inline action or detail is reachable from a sheet.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/editor_screen.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/plan_screen.dart';
import 'package:tutor/ui/progress_screen.dart';
import 'package:tutor/ui/review_screen.dart';
import 'package:tutor/util/ulid.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/learn_finders.dart';
import '../support/services.dart';
import '../support/ui.dart';

const _phone = Size(412, 900);

Future<void> _longPress(WidgetTester t, Finder f) async {
  await t.longPress(f);
  await t.pumpAndSettle();
}

Future<void> _tap(WidgetTester t, Finder f) async {
  await t.tap(f);
  await t.pumpAndSettle();
}

/// Phone: Refresh sits in the ⋮ menu.
Future<void> _refresh(WidgetTester t) async {
  await _tap(t, bySpoken('More'));
  await _tap(t, find.byIcon(Icons.refresh));
}

Finder _subject(String id) => find.byKey(ValueKey('subject-tile-$id'));

Future<TutorServices> _home(WidgetTester t, FakeRtdb db, FakeStream s) async {
  final services = await fixtureServices(db, s);
  await pumpScreen(
    t,
    HomeScreen(services: services, onSignedOut: () {}),
    size: _phone,
  );
  return services;
}

void main() {
  testWidgets('Home: tap picks or plans; the sheet opens the plan', (t) async {
    final db = fixtureDb();
    await _home(t, db, FakeStream());
    await _tap(t, _subject('garden'));
    expect(find.byType(PlanScreen), findsOneWidget); // draft -> Plan
    await t.pageBack();
    await t.pumpAndSettle();

    await _longPress(t, _subject('car'));
    expect(spoken('1/4 modules reviewed'), findsOneWidget);
    expect(controlByLabel('Cards'), findsOneWidget);
    await _tap(t, controlByLabel('Plan'));
    expect(find.byType(PlanScreen), findsOneWidget);
    await t.pageBack();
    await t.pumpAndSettle();
    expect(find.byType(BottomSheet), findsNothing);

    db.root = setAt(db.root, 'tutor/v1/subjects/garden/meta/status', 'active');
    db.root = setAt(db.root, 'tutor/v1/rev/catalog', 8);
    await _refresh(t);
    await _tap(t, _subject('garden'));
    expect(getAt(db.root, 'tutor/v1/prefs/current_subject'), 'garden');
  });

  testWidgets('Home: Review only and Try again from sheets', (t) async {
    final db = fixtureDb();
    db.root = setAt(db.root, 'tutor/v1/subjects/car/meta/status', 'completed');
    db.root = setAt(db.root, 'tutor/v1/subjects/garden/meta/status', 'failed');
    final stream = FakeStream();
    await _home(t, db, stream);
    await _longPress(t, _subject('car'));
    await t.tap(controlByLabel('Review only'));
    await sent(t);
    expect((await answer(t, db, stream))['kind'], 'subject_finish');
    await _longPress(t, _subject('garden'));
    await t.tap(controlByLabel('Try again'));
    await sent(t);
    final req = await answer(t, db, stream, code: 'model_error');
    expect(req['kind'], 'subject_new');
    expect(cueContaining('failed on this turn'), findsOneWidget);
  });

  testWidgets('Home: Cards, Review due, Learn next, Go deeper', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await _home(t, db, stream);
    final month = fixtureNow - 30 * 86400000;
    await s.events.record(
      TaughtEvent(subject: 'car', card: 'eng-crank', at: month),
    );
    await _refresh(t);
    await _longPress(t, _subject('car'));
    await _tap(t, controlByLabel('Cards'));
    expect(find.byType(EditorScreen), findsOneWidget);
    await t.pageBack();
    await t.pumpAndSettle();
    await _longPress(t, _subject('car'));
    await _tap(t, controlByLabel('Review (1 due)').last);
    expect(find.byType(ReviewScreen), findsOneWidget);
    await t.pageBack();
    await t.pumpAndSettle();

    db.root = setAt(db.root, 'tutor/v1/subjects/garden/meta/status', 'active');
    db.root = setAt(db.root, 'tutor/v1/subjects/car/meta/status', 'completed');
    db.root = setAt(db.root, 'tutor/v1/rev/catalog', 8);
    await _refresh(t);
    await _longPress(t, _subject('garden'));
    await _tap(t, controlByLabel('Learn this next'));
    expect(getAt(db.root, 'tutor/v1/prefs/current_subject'), 'garden');
    await _longPress(t, _subject('car'));
    await t.tap(controlByLabel('Go deeper'));
    await sent(t);
    final req = await answer(t, db, stream);
    expect(req['body'], {'subject': 'car', 'choice': 'go_deeper'});
  });

  testWidgets('Home: "+" drafts a plan, then Back lands on Home', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    await _home(t, db, stream);
    await _tap(t, controlByLabel('New subject'));
    await t.enterText(find.byType(TextField), 'how bridges stand');
    await t.tap(controlByLabel('Draft a plan'));
    await sent(t);
    expect(cueContaining('drafts a plan'), findsOneWidget);
    await answer(t, db, stream, data: {'subject': 'garden'});
    expect(spoken('Modules (teaching order)'), findsOneWidget);
    await t.pageBack();
    await t.pumpAndSettle();
    expect(find.byType(AlertDialog), findsNothing);
    expect(controlByLabel('New subject'), findsOneWidget);
  });

  testWidgets('Home: more subjects than fit page sideways', (t) async {
    final db = fixtureDb();
    for (var i = 0; i < 24; i++) {
      db.root = setAt(db.root, 'tutor/v1/subjects/extra$i/meta', {
        'title': 'Extra $i',
        'goal': 'g',
        'status': 'failed',
        'created': 1,
        'rev': 1,
        'origin': 'generated',
      });
    }
    await _home(t, db, FakeStream());
    expect(find.byKey(const ValueKey('fit-grid-dot-1')), findsOneWidget);
    expect(controlByLabel('New subject').hitTestable(), findsNothing);
    for (var i = 0; i < 5; i++) {
      await t.drag(find.byType(PageView), const Offset(-400, 0));
      await t.pumpAndSettle();
    }
    expect(controlByLabel('New subject').hitTestable(), findsOneWidget);
  });

  testWidgets('Plan: chips switch; sheets Retry and Review', (t) async {
    final db = fixtureDb();
    db.root = setAt(db.root, 'tutor/v1/subjects/car/plan/history', [
      {'rev': 1, 'comment': 'less history', 'at': 1},
    ]);
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    final pc = EventLog(
      client: s.client,
      kv: MemoryKv(),
      dev: '7c1e9a52-3b4d-4f60-8a1b-2c3d4e5f6a70',
      ulid: UlidGenerator(),
    );
    await pc.record(
      TaughtEvent(subject: 'car', card: 'fuel-spark', at: fixtureNow),
    );
    await pc.flush();
    await s.events.pull();
    await pumpScreen(
      t,
      PlanScreen(services: s, subject: 'car'),
      size: _phone,
    );
    await _tap(t, chipSpoken('Revisions'));
    expect(chipSelected(t, 'Revisions'), isTrue);
    expect(spoken('rev 1: less history'), findsOneWidget);
    expect(find.text('less history'), findsOneWidget); // the comment: content
    await _tap(t, chipSpoken('Modules'));
    expect(chipSelected(t, 'Modules'), isTrue);

    await _tap(t, find.byKey(const ValueKey('module-tile-3'))); // Brakes
    await t.tap(controlByLabel('Retry'));
    await sent(t);
    expect((await answer(t, db, stream))['kind'], 'plan_approve');
    await _tap(t, find.byKey(const ValueKey('module-tile-1'))); // Fuel
    expect(bySpoken('recall 33%'), findsWidgets);
    await _tap(t, controlByLabel('Review this module'));
    expect(find.text('What ignites the mixture?'), findsOneWidget);
  });

  testWidgets('Progress: chips, All days, a subject sheet', (t) async {
    final s = await fixtureServices(fixtureDb(), FakeStream());
    await pumpScreen(t, ProgressScreen(services: s), size: _phone);
    expect(find.bySemanticsLabel(RegExp('^min per day, 7 days')), findsOne);
    await _tap(t, chipSpoken('Taught'));
    expect(find.bySemanticsLabel(RegExp('^cards per day')), findsOne);
    await _tap(t, controlByLabel('All days'));
    expect(find.text('2026-10-12'), findsOneWidget);
    expect(find.text('2026-09-29'), findsOneWidget);
    await t.tapAt(const Offset(10, 10));
    await t.pumpAndSettle();
    await _tap(t, find.byKey(const ValueKey('subject-stat-0')));
    expect(bySpoken('recall 85%'), findsWidgets);
    expect(bySpoken('reviewed', prefix: true), findsWidgets);
    expect(find.text('Brakes'), findsOneWidget);
  });

  testWidgets('Progress: no days yet', (t) async {
    final db = fixtureDb();
    db.root = setAt(db.root, 'tutor/v1/stats/days', null);
    final s = await fixtureServices(db, FakeStream());
    await pumpScreen(t, ProgressScreen(services: s), size: _phone);
    expect(spokenHas('No days yet'), findsOneWidget);
    expect(controlByLabel('All days'), findsNothing);
  });

  testWidgets('Progress: no approved plans yet', (t) async {
    final s = services(fixtureDb(), FakeStream()); // nothing cached
    await pumpScreen(t, ProgressScreen(services: s), size: _phone);
    expect(spoken('No approved plans yet.'), findsOneWidget);
  });
}
