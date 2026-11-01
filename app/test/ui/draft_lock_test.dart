// While a plan draft or redraft is in flight its text box and button are
// locked (greyed), a stalled request frees the button for a resend, success
// clears the text and failure keeps it for the retry.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/new_subject_field.dart';
import 'package:tutor/ui/plan_screen.dart';

import '../support/fake_stream.dart';
import '../support/ui.dart';

const _comment = 'Comment (e.g. "less history, more maintenance")';

TextField _field(WidgetTester t, Finder f) => t.widget<TextField>(f);

VoidCallback? _button<T extends ButtonStyleButton>(
  WidgetTester t,
  String label,
) => t.widget<T>(find.widgetWithText(T, label)).onPressed;

void main() {
  testWidgets('home: locked while drafting, cleared on success', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      HomeScreen(services: s, onSignedOut: () {}),
      size: const Size(412, 1400),
    );
    final box = find.byType(TextField);
    await t.enterText(box, 'how bridges stand');
    await t.tap(find.text('Draft a plan'));
    await sent(t);
    expect(_field(t, box).enabled, isFalse);
    expect(_button<FilledButton>(t, 'Draft a plan'), isNull);

    await answer(t, db, stream, code: 'bad_request');
    expect(_field(t, box).enabled, isTrue);
    expect(_field(t, box).controller!.text, 'how bridges stand');
    expect(_button<FilledButton>(t, 'Draft a plan'), isNotNull);

    await t.tap(find.text('Draft a plan'));
    await sent(t);
    await answer(t, db, stream, data: {'subject': 'garden'});
    await t.pageBack();
    await t.pumpAndSettle();
    expect(_field(t, box).controller!.text, isEmpty);
    expect(_field(t, box).enabled, isTrue);
  });

  testWidgets('home: a stalled draft frees the button, not the box', (t) async {
    final s = await fixtureServices(fixtureDb(), FakeStream());
    final runner = RequestRunner(s.relay);
    addTearDown(runner.dispose);
    await pumpScreen(
      t,
      Scaffold(
        body: NewSubjectField(runner: runner, onSubmit: (_) {}),
      ),
    );
    runner.status.value = const RelayQueued();
    await t.pump();
    expect(_button<FilledButton>(t, 'Draft a plan'), isNull);
    runner.stalled.value = true;
    await t.pump();
    expect(_button<FilledButton>(t, 'Draft a plan'), isNotNull);
    expect(_field(t, find.byType(TextField)).enabled, isFalse);
  });

  testWidgets('plan: comment locked while redrafting', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      PlanScreen(services: s, subject: 'garden'),
      size: const Size(1000, 2400),
    );
    final box = find.widgetWithText(TextField, _comment);
    await t.enterText(box, 'less soil');
    await t.tap(find.text('Redraft with this comment'));
    await sent(t);
    expect(_field(t, box).enabled, isFalse);
    expect(_button<OutlinedButton>(t, 'Redraft with this comment'), isNull);

    await answer(t, db, stream, code: 'plan_conflict');
    expect(_field(t, box).enabled, isTrue);
    expect(_field(t, box).controller!.text, 'less soil');
    expect(_button<OutlinedButton>(t, 'Redraft with this comment'), isNotNull);
  });
}
