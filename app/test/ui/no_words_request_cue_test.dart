// textgate guard for the request cues: relayCue's kinds and glyphs, and
// the request status line (offline, blocked, cap, locked, model error,
// busy phases) painting no app words. Split from no_words_home_test.dart.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/relay/blocked.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/relay_cue.dart';
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
}
