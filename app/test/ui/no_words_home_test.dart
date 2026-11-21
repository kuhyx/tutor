// textgate guard for the shell, Home and its dialogs: the PC banner, sign-in
// failure, display size, flag, report and today paint no app words (request
// cues: no_words_request_cue_test.dart).
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/plan/today_plan.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/flag_dialog.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/sign_in_screen.dart';
import 'package:tutor/ui/today_screen.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/no_words.dart';
import '../support/ui.dart';

void main() {
  testWidgets('PC offline banner is a cue', (t) async {
    final presence = ValueNotifier(PcPresence.offline);
    await pumpScreen(t, Scaffold(body: PcOfflineBanner(presence)));
    expect(cueOfKind(CueKind.offline), findsOneWidget);
    expectNoWords(t, 'banner');
    presence.value = PcPresence.online;
    await t.pump();
    expect(find.byType(CueChip), findsNothing);
  });

  testWidgets('a failed sign-in is a red cue, no sentence', (t) async {
    final s = await fixtureServices(fixtureDb(), FakeStream());
    await pumpScreen(
      t,
      SignInScreen(
        services: s,
        onSignedIn: () {},
        supported: true,
        tokenFetcher: () async => null,
      ),
    );
    expect(cueOfKind(CueKind.error), findsNothing);
    await t.tap(controlByLabel('Sign in with Google'));
    await t.pumpAndSettle();
    expect(cueOfKind(CueKind.error), findsOneWidget);
    expectNoWords(t, 'sign-in failed');
  });

  testWidgets('desktop sign-in notice is a cue', (t) async {
    final s = await fixtureServices(fixtureDb(), FakeStream());
    await pumpScreen(
      t,
      SignInScreen(services: s, onSignedIn: () {}, supported: false),
    );
    expect(cueOfKind(CueKind.offline), findsOneWidget);
    expectNoWords(t, 'sign-in desktop');
  });

  testWidgets('dialogs paint no words: display size, flag, report', (t) async {
    final s = await fixtureServices(fixtureDb(), FakeStream());
    await pumpScreen(t, HomeScreen(services: s, onSignedOut: () {}));
    await t.tap(find.byIcon(Icons.more_vert));
    await t.pumpAndSettle();
    expectNoWords(t, 'home menu');
    await t.tap(bySpoken('Display size').first);
    await t.pumpAndSettle();
    expectNoWords(t, 'display size');
    await t.tap(glyphsLabelled('Done'));
    await t.pumpAndSettle();

    await t.tap(find.byIcon(Icons.more_vert));
    await t.pumpAndSettle();
    await t.tap(bySpoken('Report a problem').first);
    await t.pumpAndSettle();
    expectNoWords(t, 'report');
    await t.tap(glyphsLabelled('Save report'));
    await t.pumpAndSettle();
    expect(cueOfKind(CueKind.error), findsOneWidget);
    expectNoWords(t, 'report error');
    await t.tap(glyphsLabelled('Cancel'));
    await t.pumpAndSettle();

    late BuildContext ctx;
    await pumpScreen(
      t,
      Builder(
        builder: (context) {
          ctx = context;
          return const SizedBox();
        },
      ),
    );
    unawaited(askFlagReason(ctx));
    await t.pumpAndSettle();
    expectNoWords(t, 'flag');
    expect(
      fieldByLabel('What is wrong? (e.g. "the answer is wrong")'),
      findsOneWidget,
    );
    await t.tap(glyphsLabelled('Cancel'));
    await t.pumpAndSettle();
    unawaited(showReport(ctx, s, route: '/', msg: 'm1', preview: 'text'));
    await t.pumpAndSettle();
    expectNoWords(t, 'report about a message');
  });

  testWidgets('today keeps only approved words and content', (t) async {
    final s = await fixtureServices(fixtureDb(), FakeStream());
    addTearDown(s.focus.dispose);
    await pumpScreen(
      t,
      TodayScreen(
        services: s,
        plan: TodayPlan.fromJson({
          'date': '2026-11-03',
          'steps': [
            {
              'id': 's1',
              'title': 'Step title',
              'what': 'Do thing.',
              'kind': 'coach',
              'target': 'x',
              'done': false,
            },
          ],
          'current': 's1',
        }),
        openHome: () {},
      ),
      settle: false,
    );
    await sent(t);
    expectNoWords(t, 'today');
    expect(find.text('Step title'), findsOneWidget); // content stays
  });
}
