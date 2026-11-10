// textgate guard for the shell, Home and its dialogs: request cues (offline,
// blocked, cap, locked, model error, busy phases), the PC banner, sign-in
// failure, display size, flag, report and today paint no app words.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/plan/today_plan.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/relay/blocked.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/flag_dialog.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/relay_cue.dart';
import 'package:tutor/ui/sign_in_screen.dart';
import 'package:tutor/ui/today_screen.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/no_words.dart';
import '../support/ui.dart';

const _blockedCap = Blocked(
  code: dailyNewCap,
  next: BlockedNext.liftCap,
  newToday: 10,
  newCap: 10,
);
const _locked = Blocked(
  code: lockedCode,
  next: BlockedNext.reviewModule,
  module: 'm1',
  moduleTitle: 'Brakes',
);
const _noCard = Blocked(next: BlockedNext.reviewsDue, dueAt: 1);

void main() {
  group('relayCue', () {
    test('kinds and glyphs', () {
      expect(relayCue(null), isNull);
      expect(relayCue(const RelayDone({})), isNull);
      expect(relayCue(const RelayQueued())?.kind, CueKind.pending);
      expect(
        relayCue(const RelayWorking(Phase.thinking, 1))?.kind,
        CueKind.pending,
      );
      final off = relayCue(RelayNotSent(Exception('x')));
      expect(off?.kind, CueKind.error);
      expect(off?.icon, Icons.cloud_off);
      expect(
        relayCue(const RelayFailed(code: 'model_error', text: 'x'))?.kind,
        CueKind.error,
      );
      final lost = relayCue(const RelayQueued(), stalled: 'No reply');
      expect(lost?.kind, CueKind.error);
      expect(lost?.semanticLabel, 'No reply');
    });

    test('a block is calm and shows what fixes it', () {
      final cue = relayCue(
        const RelayFailed(
          code: dailyNewCap,
          kind: 'blocked_cap',
          text: 'x',
          blocked: _blockedCap,
        ),
      );
      expect(cue?.kind, CueKind.blocked);
      expect(cue?.icon, Icons.add_circle_outline);
      expect(kindIcon('blocked_locked_review'), Icons.replay);
      expect(kindIcon('blocked_no_card_due'), Icons.schedule);
      expect(kindIcon('blocked_locked'), Icons.lock_outline);
    });
  });

  group('request status line', () {
    final statuses = <String, RelayStatus>{
      'queued': const RelayQueued(),
      'claimed': const RelayWorking(Phase.claimed, 1),
      'thinking': const RelayWorking(Phase.thinking, 1),
      'images': const RelayWorking(Phase.images, 1),
      'publishing': const RelayWorking(Phase.publishing, 1),
      'offline': RelayNotSent(Exception('down')),
      'model error': const RelayFailed(
        code: 'model_error',
        text: 'The tutor model failed on this turn.',
        retry: true,
      ),
      'cap': const RelayFailed(
        code: dailyNewCap,
        text: 'cap',
        blocked: _blockedCap,
      ),
      'locked': const RelayFailed(
        code: lockedCode,
        text: 'locked',
        blocked: _locked,
      ),
      'no card': const RelayFailed(
        code: noCardLeft,
        text: 'none',
        blocked: _noCard,
      ),
    };
    for (final MapEntry(key: name, value: status) in statuses.entries) {
      testWidgets('$name paints no words', (t) async {
        final s = await fixtureServices(fixtureDb(), FakeStream());
        final runner = RequestRunner(s.relay)..status.value = status;
        addTearDown(runner.dispose);
        await pumpScreen(
          t,
          Scaffold(body: RequestStatusLine(runner)),
          settle: false,
        );
        await sent(t);
        expectNoWords(t, name);
        final cue = relayCue(status)!;
        expect(find.byType(CueChip), findsOneWidget);
        expect(t.widget<CueChip>(find.byType(CueChip)).kind, cue.kind);
      });
    }

    testWidgets('retry and dismiss are glyph buttons', (t) async {
      final s = await fixtureServices(fixtureDb(), FakeStream());
      final runner = RequestRunner(s.relay)
        ..status.value = const RelayFailed(
          code: 'model_error',
          text: 'x',
          retry: true,
        );
      addTearDown(runner.dispose);
      await pumpScreen(
        t,
        Scaffold(body: RequestStatusLine(runner)),
        settle: false,
      );
      expect(glyphsLabelled('Retry'), findsOneWidget);
      await t.tap(glyphsLabelled('Dismiss'));
      await t.pump();
      expect(runner.status.value, isNull);
      expect(find.byType(CueChip), findsNothing);
    });

    testWidgets('the shake stands still when animations are off', (t) async {
      final s = await fixtureServices(fixtureDb(), FakeStream());
      final runner = RequestRunner(s.relay)
        ..status.value = RelayNotSent(Exception('down'));
      addTearDown(runner.dispose);
      t.platformDispatcher.accessibilityFeaturesTestValue =
          const FakeAccessibilityFeatures(disableAnimations: true);
      addTearDown(t.platformDispatcher.clearAccessibilityFeaturesTestValue);
      await pumpScreen(
        t,
        Scaffold(body: RequestStatusLine(runner)),
        settle: false,
      );
      await t.pump(const Duration(milliseconds: 100));
      expect(t.hasRunningAnimations, isFalse);
    });
  });

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
