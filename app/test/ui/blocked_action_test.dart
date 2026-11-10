// A blocking result is a call to action, not an error: one "why" line, a
// primary button that fixes it, a secondary one where it helps; no red,
// never the worker's raw text.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/ui/session/session_screen.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

/// Opens the car Session as Continue learning does and answers [code].
Future<(FakeRtdb, FakeStream)> _blocked(
  WidgetTester t,
  String code,
  Map<String, Object?> extra, {
  String error = 'raw worker text',
  bool taught = false,
}) async {
  final db = fixtureDb();
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  if (taught) {
    final month = DateTime.fromMillisecondsSinceEpoch(fixtureNow)
        .subtract(const Duration(days: 30))
        .millisecondsSinceEpoch;
    for (final c in ['eng-strokes', 'eng-crank', 'fuel-spark']) {
      await s.events.record(TaughtEvent(subject: 'car', card: c, at: month));
    }
  }
  await pumpScreen(
    t,
    SessionScreen(services: s, subject: 'car', resume: true),
    settle: false,
  );
  await sent(t);
  await answer(
    t,
    db,
    stream,
    code: code,
    error: error,
    extra: extra,
    settle: false,
  );
  return (db, stream);
}

final Finder _rawWorkerText = find.byWidgetPredicate(
  (w) => w is CueChip && w.semanticLabel.contains('raw worker text'),
);

/// A block is a call to action: an amber cue, never the red error cue.
void _noRed(WidgetTester t) {
  expect(cueOfKind(CueKind.error), findsNothing);
  expect(cueOfKind(CueKind.blocked), findsOneWidget);
}

void main() {
  testWidgets('daily_new_cap -> Learn more anyway sends lift_cap', (t) async {
    final (db, _) = await _blocked(t, 'daily_new_cap', {
      'subject_title': 'How a car works',
      'new_today': 25,
      'new_cap': 25,
      'module_title': 'Fuel and ignition',
      'due_in_subject': 2,
      'next': 'lift_cap',
    }, error: 'Ten new cards today already. Reviews still work.');
    expect(
      cueLabelled(
        'You learned 25 new cards today (the daily limit). '
        '“Fuel and ignition” is open.',
      ),
      findsOneWidget,
    );
    expect(bySpoken('Reviews still work', prefix: true), findsNothing);
    expect(controlByLabel('Review this subject (2 due)'), findsOneWidget);
    _noRed(t);

    await t.tap(controlByLabel('Learn more anyway'));
    await sent(t);
    final (_, req) = lastRequest(db);
    expect(req['kind'], 'session_start');
    final body = req['body'] as Map<String, dynamic>;
    expect(body['lift_cap'], isTrue);
    expect(body['subject'], 'car');
    expect(body['resume'], isTrue);
  });

  testWidgets('daily_new_cap, no fields: still the button', (t) async {
    await _blocked(t, 'daily_new_cap', const {});
    expect(cueLabelled("You reached today's limit of new cards."), findsOne);
    expect(controlByLabel('Learn more anyway'), findsOneWidget);
    expect(controlByLabel('Review this subject', prefix: true), findsNothing);
    expect(_rawWorkerText, findsNothing);
  });

  testWidgets('Review this subject opens only its due cards', (t) async {
    await _blocked(t, 'no_card_left', {
      'subject_title': 'How a car works',
      'next': 'none',
      'due_in_subject': 3,
    }, taught: true);
    _noRed(t);
    await t.tap(controlByLabel('Review this subject (3 due)'));
    await sent(t);
    await sent(t);
    expect(controlByLabel('Review: How a car works'), findsOneWidget);
    expect(controlByLabel('3 left'), findsOneWidget);
  });

  testWidgets('locked -> Review <module> opens the module review', (t) async {
    await _blocked(t, 'locked', {
      'subject_title': 'How a car works',
      'next': 'review_module',
      'module': 'fuel',
      'module_title': 'Fuel and ignition',
    }, taught: true);
    expect(
      cueLabelled('That is locked until “Fuel and ignition” is reviewed.'),
      findsOneWidget,
    );
    _noRed(t);
    await t.tap(controlByLabel('Review Fuel and ignition'));
    await sent(t);
    await sent(t);
    expect(controlByLabel('Review: Fuel and ignition'), findsOneWidget);
  });

  testWidgets('locked, nothing to do: the line, no button', (t) async {
    await _blocked(t, 'locked', const {'next': 'none'});
    expect(
      cueLabelled('That is locked until earlier modules are reviewed.'),
      findsOneWidget,
    );
    expect(_rawWorkerText, findsNothing);
    expect(glyphsLabelled('Review Fuel and ignition'), findsNothing);
    _noRed(t);
  });
}
