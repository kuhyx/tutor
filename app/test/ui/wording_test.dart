// Three plain words, never "mastered": Done (taught), Known (concepts used
// correctly), Recalled (right 20 h after learning); modules are done or
// reviewed. Each comes with a one-line explanation as a tooltip.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/progress/terms.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/editor_screen.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/plan_screen.dart';
import 'package:tutor/ui/progress_screen.dart';
import 'package:tutor/ui/session/message_tile.dart';
import 'package:tutor/ui/session/session_screen.dart';
import 'package:tutor/widgets/spoken_label.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/learn_finders.dart';
import '../support/ui.dart';

final Finder _mastered = find.textContaining(RegExp('[Mm]aster'));

void main() {
  testWidgets('Home: n/m modules reviewed, explained', (t) async {
    final s = await fixtureServices(fixtureDb(), FakeStream());
    await pumpScreen(t, HomeScreen(services: s, onSignedOut: () {}));
    expect(bySpoken('1/4 modules reviewed'), findsOneWidget);
    expect(_mastered, findsNothing);
  });

  testWidgets('Home: n/m cards recalled, explained', (t) async {
    final s = await fixtureServices(fixtureDb(), FakeStream());
    await s.events.record(
      TaughtEvent(
        subject: 'car',
        card: 'eng-strokes',
        at: fixtureNow - 30 * 86400000,
      ),
    );
    await s.events.record(
      ReviewEvent(
        subject: 'car',
        card: 'eng-strokes',
        at: fixtureNow,
        grade: Grade.good,
        rev: 1,
      ),
    );
    await pumpScreen(t, HomeScreen(services: s, onSignedOut: () {}));
    expect(
      find.byWidgetPredicate(
        (w) =>
            w is SpokenLabel &&
            RegExp(r'^1/\d+ cards recalled').hasMatch(w.semanticLabel),
      ),
      findsOneWidget,
    );
    expect(bySpoken('1/4 modules reviewed'), findsOneWidget);
    expect(_mastered, findsNothing);
  });

  testWidgets('Plan and Progress: module badges done / reviewed', (t) async {
    final s = await fixtureServices(fixtureDb(), FakeStream());
    // fuel's one catalog card taught: the module is done.
    await s.events.record(
      TaughtEvent(subject: 'car', card: 'fuel-spark', at: fixtureNow),
    );
    await pumpScreen(t, PlanScreen(services: s, subject: 'car'));
    expect(bySpoken('reviewed · 3 cards', prefix: true), findsOneWidget);
    expect(bySpoken('done · 3 cards', prefix: true), findsOneWidget);
    expect(spokenHas('Reviewed: every card'), findsWidgets);
    expect(spokenHas('Done: '), findsWidgets);
    expect(_mastered, findsNothing);
    await pumpScreen(t, ProgressScreen(services: s));
    expect(spoken('recall 85%'), findsOneWidget);
    expect(spokenHas('Reviewed: every card'), findsWidgets);
    expect(_mastered, findsNothing);
  });

  testWidgets('Cards view: done / recalled, explained', (t) async {
    final s = await fixtureServices(fixtureDb(), FakeStream());
    for (final c in ['eng-strokes', 'eng-crank']) {
      await s.events.record(
        TaughtEvent(subject: 'car', card: c, at: fixtureNow - 30 * 86400000),
      );
    }
    await s.events.record(
      ReviewEvent(
        subject: 'car',
        card: 'eng-strokes',
        at: fixtureNow,
        grade: Grade.good,
        rev: 1,
      ),
    );
    await pumpScreen(t, EditorScreen(services: s, subject: 'car'));
    expect(spokenHas('1 recalled'), findsWidgets);
    expect(spokenHas(recalledHelp), findsWidgets);
    expect(spokenHas(doneHelp), findsWidgets);
    expect(_mastered, findsNothing);
  });

  testWidgets('Session: Known concepts, explained', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      SessionScreen(services: s, now: () => DateTime(2030)),
      settle: false,
    );
    const base = 'tutor/v1/sessions/$fixtureLiveSid';
    for (final path in ['tutor/v1/live', '$base/meta', '$base/msgs']) {
      stream.emit(path, RtdbPut('/', getAt(db.root, path)));
      await t.pump();
    }
    await t.pumpAndSettle();
    expect(bySpoken('Known'), findsWidgets);
    expect(_mastered, findsNothing);
  });

  testWidgets('a turn names newly known concepts', (t) async {
    await pumpScreen(
      t,
      const Scaffold(
        body: MessageTile(
          message: Message(
            role: 'tutor',
            text: 'Right.',
            masteredNew: ['intake stroke'],
          ),
        ),
      ),
    );
    expect(find.text('intake stroke'), findsOneWidget);
    expect(bySpoken('Known'), findsOneWidget);
  });

  test('locked reads "reviewed"', () {
    expect(headlineFor('locked'), contains('earlier modules are reviewed'));
  });
}
