// A blocking result is a call to action, not an error: one "why" line, a
// primary button that fixes it, a secondary one where it helps; no red,
// never the worker's raw text.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
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

void _noRed(WidgetTester t) {
  final error = Theme.of(t.element(find.byType(SessionScreen))).colorScheme;
  final red = t
      .widgetList<Text>(find.byType(Text))
      .where((w) => w.style?.color == error.error);
  expect(red.map((w) => w.data), isEmpty);
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
      find.text(
        'You learned 25 new cards today (the daily limit). '
        '“Fuel and ignition” is open.',
      ),
      findsOneWidget,
    );
    expect(find.textContaining('Reviews still work'), findsNothing);
    expect(find.text('Review this subject (2 due)'), findsOneWidget);
    _noRed(t);

    await t.tap(find.text('Learn more anyway'));
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
    expect(find.text("You reached today's limit of new cards."), findsOne);
    expect(find.text('Learn more anyway'), findsOneWidget);
    expect(find.textContaining('Review this subject'), findsNothing);
    expect(find.textContaining('raw worker text'), findsNothing);
  });

  testWidgets('Review this subject opens only its due cards', (t) async {
    await _blocked(t, 'no_card_left', {
      'subject_title': 'How a car works',
      'next': 'none',
      'due_in_subject': 3,
    }, taught: true);
    _noRed(t);
    await t.tap(find.text('Review this subject (3 due)'));
    await sent(t);
    await sent(t);
    expect(find.text('Review: How a car works'), findsOneWidget);
    expect(find.textContaining('3 left'), findsOneWidget);
  });

  testWidgets('locked -> Review <module> opens the module review', (t) async {
    await _blocked(t, 'locked', {
      'subject_title': 'How a car works',
      'next': 'review_module',
      'module': 'fuel',
      'module_title': 'Fuel and ignition',
    }, taught: true);
    expect(
      find.text('That is locked until “Fuel and ignition” is reviewed.'),
      findsOneWidget,
    );
    _noRed(t);
    await t.tap(find.text('Review Fuel and ignition'));
    await sent(t);
    await sent(t);
    expect(find.text('Review: Fuel and ignition'), findsOneWidget);
  });

  testWidgets('locked, nothing to do: the line, no button', (t) async {
    await _blocked(t, 'locked', const {'next': 'none'});
    expect(
      find.text('That is locked until earlier modules are reviewed.'),
      findsOneWidget,
    );
    expect(find.textContaining('raw worker text'), findsNothing);
    expect(find.textContaining(RegExp('^Review ')), findsNothing);
    _noRed(t);
  });
}
