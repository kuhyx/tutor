// textgate guard, learning screens: Review, Drill, Editor, Plan, Progress and
// their dialogs paint no app words in any state (only glyphs, numbers and
// content). Complements no_words_test.dart (one frame per route).
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/drill/anki_sync.dart';
import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/editor_screen.dart';
import 'package:tutor/ui/new_cap_dialog.dart';
import 'package:tutor/ui/plan_screen.dart';
import 'package:tutor/ui/progress_screen.dart';
import 'package:tutor/ui/review_screen.dart';

import '../support/drill.dart';
import '../support/fake_stream.dart';
import '../support/learn_finders.dart';
import '../support/no_words.dart';
import '../support/ui.dart';

const _phone = Size(412, 900);
const _wide = Size(1100, 2400);

Future<void> _taught(EventLog events, List<String> cards) async {
  final at = fixtureNow - 30 * 86400000;
  for (final c in cards) {
    await events.record(TaughtEvent(subject: 'car', card: c, at: at));
  }
}

void main() {
  for (final size in [_phone, _wide]) {
    final at = size == _phone ? 'phone' : 'wide';

    testWidgets('review: front, answer, earlier rating, end ($at)', (t) async {
      final s = await fixtureServices(fixtureDb(), FakeStream());
      await _taught(s.events, ['eng-strokes', 'eng-crank']);
      final then = DateTime.fromMillisecondsSinceEpoch(fixtureNow);
      await pumpScreen(
        t,
        ReviewScreen(services: s, now: () => then),
        size: size,
      );
      expectNoWords(t, 'review front');
      await t.tap(spoken('Show answer (Space)'));
      await t.pumpAndSettle();
      expectNoWords(t, 'review answer');
      await t.tap(spoken('3 Good'));
      await t.pumpAndSettle();
      await t.tap(spoken('Back'));
      await t.pumpAndSettle();
      expectNoWords(t, 'review earlier rating');
      await t.tap(spoken('Flag (F)'));
      await t.pumpAndSettle();
      expectNoWords(t, 'review flag dialog');
      await t.tap(spoken('Cancel'));
      await t.pumpAndSettle();
      await t.tap(spoken('1 Again'));
      await t.pumpAndSettle();
      await t.tap(spoken('Show answer (Space)'));
      await t.pumpAndSettle();
      await t.tap(spoken('3 Good'));
      await t.pumpAndSettle();
      expect(spokenHas('All done'), findsOneWidget);
      expectNoWords(t, 'review end');
    });

    testWidgets('review: nothing due ($at)', (t) async {
      final s = await fixtureServices(fixtureDb(), FakeStream());
      await pumpScreen(t, ReviewScreen(services: s), size: size);
      expect(spokenHas('Nothing due'), findsOneWidget);
      expectNoWords(t, 'review nothing due');
    });

    testWidgets('drill: question, wrong, right, empty, failed ($at)', (
      t,
    ) async {
      final db = fixtureDb();
      final stream = FakeStream();
      final s = await fixtureServices(db, stream);
      await pumpScreen(
        t,
        ReviewScreen(
          services: s,
          drill: true,
          unavailable: const Unavailable(until: kResetsAt, reason: 'limit'),
          anki: AnkiSync(relay: s.relay, launcher: FakeLauncher()),
        ),
        size: size,
        settle: false,
      );
      await answer(t, db, stream, data: drillQuestion());
      expectNoWords(t, 'drill question + banner + anki');
      await t.tap(find.text('Opens valves'));
      await sent(t);
      await answer(t, db, stream, data: drillGrade(0));
      expectNoWords(t, 'drill wrong');
      await t.tap(spoken('Next (Space)'));
      await sent(t);
      await answer(t, db, stream, data: drillQuestion());
      await t.tap(find.text('Turns pistons into rotation'));
      await sent(t);
      await answer(t, db, stream, data: drillGrade(1));
      expectNoWords(t, 'drill right');
      await t.tap(spoken('Next (Space)'));
      await sent(t);
      await answer(t, db, stream, data: {'empty': true});
      expectNoWords(t, 'drill empty');
      await t.tap(spoken('Review'));
      await t.pumpAndSettle();
      await t.tap(spoken('Drill').last);
      await sent(t);
      await answer(t, db, stream, code: 'worker_error');
      expectNoWords(t, 'drill failed');
    });

    testWidgets('editor: module open, removed cards, card form ($at)', (
      t,
    ) async {
      final db = fixtureDb();
      const cards = 'tutor/v1/subjects/car/cards';
      Map<String, Object?> card(int order, Map<String, Object?> tutor) => {
        'module': 'engine',
        'order': order,
        'front': 'What is a piston?',
        'back': 'An answer.',
        'source': 'https://en.wikipedia.org/wiki/Piston',
        'excerpt': 'a piston is a moving part that slides in a cylinder',
        'rev': 1,
        'origin': 'edited',
        'suspended': tutor.containsKey('removed'),
        'tutor': tutor,
      };
      db.root = setAt(db.root, '$cards/eng-old', card(4, {'removed': 1}));
      db.root = setAt(db.root, '$cards/eng-new', card(5, {'added': 1}));
      final s = await fixtureServices(db, FakeStream());
      await _taught(s.events, ['eng-strokes']);
      await pumpScreen(
        t,
        EditorScreen(services: s, subject: 'car'),
        size: size,
      );
      expectNoWords(t, 'editor list');
      await t.tap(find.text('The four-stroke engine'));
      await t.pumpAndSettle();
      expectNoWords(t, 'editor module open');
      await t.tap(spoken('Add card').first);
      await t.pumpAndSettle();
      expectNoWords(t, 'card form with problems');
      await t.enterText(fieldLabelled('Front (question, <=25 words)'), 'Q?');
      await t.pumpAndSettle();
      expectNoWords(t, 'card form typed');
    });

    testWidgets('plan: approved, revisions, drafting, failed ($at)', (t) async {
      final db = fixtureDb();
      db.root = setAt(db.root, 'tutor/v1/subjects/car/plan/history', [
        {'rev': 1, 'comment': 'less history', 'at': 1},
      ]);
      final s = await fixtureServices(db, FakeStream());
      await _taught(s.events, ['fuel-spark']);
      await pumpScreen(
        t,
        PlanScreen(services: s, subject: 'car'),
        size: size,
      );
      expectNoWords(t, 'plan approved');
      if (size == _phone) {
        await t.tap(chipSpoken('Revisions'));
        await t.pumpAndSettle();
        expectNoWords(t, 'plan revisions');
        await t.tap(chipSpoken('Modules'));
        await t.pumpAndSettle();
        await t.tap(find.byKey(const ValueKey('module-tile-0')));
        await t.pumpAndSettle();
        expectNoWords(t, 'plan module sheet');
      }
      for (final status in ['drafting', 'failed']) {
        db.root = setAt(
          db.root,
          'tutor/v1/subjects/garden/meta/status',
          status,
        );
        db.root = setAt(
          db.root,
          'tutor/v1/subjects/garden/meta/error',
          'no sources',
        );
        await pumpScreen(
          t,
          PlanScreen(services: s, subject: 'garden', key: UniqueKey()),
          size: size,
        );
        expectNoWords(t, 'plan $status');
      }
    });

    testWidgets('plan draft: edit dialog, problems ($at)', (t) async {
      final s = await fixtureServices(fixtureDb(), FakeStream());
      await pumpScreen(
        t,
        PlanScreen(services: s, subject: 'garden'),
        size: size == _phone ? const Size(412, 2600) : _wide,
      );
      expectNoWords(t, 'plan draft');
      for (var i = 0; i < 3; i++) {
        await t.tap(spoken('Move down').at(i));
        await t.pumpAndSettle();
      }
      expect(cueHas('not before it'), findsOneWidget);
      expectNoWords(t, 'plan draft with problems');
      await t.tap(spoken('Undo edits'));
      await t.pumpAndSettle();
      await t.tap(spoken('Edit').at(1));
      await t.pumpAndSettle();
      expectNoWords(t, 'edit module dialog');
    });

    testWidgets('progress: charts, sheets, nothing ($at)', (t) async {
      final db = fixtureDb();
      final s = await fixtureServices(db, FakeStream());
      await pumpScreen(t, ProgressScreen(services: s), size: size);
      expectNoWords(t, 'progress');
      if (size == _phone) {
        await t.tap(chipSpoken('Taught'));
        await t.pumpAndSettle();
        expect(chipSelected(t, 'Taught'), isTrue);
        expectNoWords(t, 'progress taught chart');
        await t.tap(spoken('All days'));
        await t.pumpAndSettle();
        expectNoWords(t, 'progress all days');
      }
      db.root = setAt(db.root, 'tutor/v1/stats/days', null);
      await pumpScreen(
        t,
        ProgressScreen(services: s, key: UniqueKey()),
        size: size,
      );
      expectNoWords(t, 'progress no days');
    });
  }

  testWidgets('new cap dialog: field, error', (t) async {
    final s = await fixtureServices(fixtureDb(), FakeStream());
    await pumpScreen(
      t,
      Builder(
        builder: (context) => TextButton(
          onPressed: () => unawaited(showNewCap(context, s.events)),
          child: const Icon(Icons.add),
        ),
      ),
    );
    await t.tap(find.byIcon(Icons.add));
    await t.pumpAndSettle();
    expectNoWords(t, 'new cap');
    await t.enterText(find.byType(TextField), '999');
    await t.tap(spoken('Save'));
    await t.pumpAndSettle();
    expect(cueHas('A number from'), findsOneWidget);
    expectNoWords(t, 'new cap error');
  });
}
