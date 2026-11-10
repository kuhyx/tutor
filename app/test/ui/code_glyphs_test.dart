// A glyph per machine code (DOCS-contract §4a): each cause paints its own
// glyph, an unknown or missing code paints today's generic one, and the
// worker's sentence stays the spoken label.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/model/codes.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/ui/code_glyphs.dart';
import 'package:tutor/ui/drill_parts.dart';
import 'package:tutor/ui/module_tile.dart';
import 'package:tutor/ui/relay_cue.dart';
import 'package:tutor/ui/session/message_tile.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/status_glyph.dart';

RelayFailed _failed(Map<String, Object?> result) => statusOf({
  'result': {'ok': false, 'at': 1, 'retry': false, ...result},
}) as RelayFailed;

Future<void> _pump(WidgetTester t, Widget w) => t.pumpWidget(
  MaterialApp(
    home: Scaffold(body: Center(child: w)),
  ),
);

void main() {
  test('C1: outage reasons paint three distinct glyphs, not the generic', () {
    IconData? of(Map<String, Object?> r) => relayCue(_failed(r))!.icon;
    final out = {
      for (final why in ['rate_limit', 'overloaded', 'network'])
        of({'code': 'claude_unavailable', 'reason': why, 'error': 'down'}),
    };
    expect(out, hasLength(3));
    expect(out, isNot(contains(genericErrorIcon)));
  });

  test('C11: five distinct phase glyphs; an unknown phase is neutral', () {
    final shown = [
      for (final p in Phase.values.where((p) => p != Phase.unknown))
        relayCue(RelayWorking(p, 1))!.icon,
    ];
    expect(shown.toSet(), hasLength(5));
    final odd = statusOf({
      'claim': {
        'by': 'pc',
        'at': 1,
        'lease_until': 9,
        'attempt': 1,
        'phase': 'dreaming',
      },
    });
    expect(odd, isA<RelayWorking>());
    expect(relayCue(odd)!.icon, Icons.more_horiz);
  });

  testWidgets('C5: each notice kind its glyph; old messages generic', (
    t,
  ) async {
    final m = Message.fromJson({
      'role': 'tutor',
      'text': 'Done.',
      'notices': ['Card removed: A', 'Card added: B', 'Card split into 2: C'],
      'notice_kinds': ['removed', 'added'],
    });
    await _pump(t, MessageTile(message: m));
    CueChip chip(String label) => t.widget<CueChip>(
      find.byWidgetPredicate((w) => w is CueChip && w.semanticLabel == label),
    );
    expect(chip('Card removed: A').icon, noticeIcon(NoticeKind.removed));
    expect(chip('Card added: B').icon, noticeIcon(NoticeKind.added));
    expect(chip('Card split into 2: C').icon, genericNoticeIcon);
    final kinds = NoticeKind.values.map(noticeIcon).toSet();
    expect(kinds, hasLength(NoticeKind.values.length));
    expect(m.toJson()['notice_kinds'], ['removed', 'added']);
    final old = Message.fromJson({
      'role': 'tutor',
      'text': 'x',
      'notices': ['Card updated: D'],
      'notice_kinds': 'bogus',
    });
    expect(old.noticeKind(0), NoticeKind.other);
  });

  test('C6: the two pause reasons paint two glyphs', () {
    final low = EngagementClock.fromJson({
      'active_seconds': 1,
      'paused_reason': 'low-effort reply',
    });
    final stalled = EngagementClock.fromJson({
      'active_seconds': 1,
      'paused_reason': 'no reply for 10 min',
    });
    expect(low.pauseKind, PauseReason.lowEffort);
    expect(stalled.pauseKind, PauseReason.stalled);
    expect(pauseIcon(low.pauseKind!), isNot(pauseIcon(stalled.pauseKind!)));
    expect(EngagementClock.fromJson({'active_seconds': 1}).pauseKind, isNull);
  });

  testWidgets('C7: a failed subject shows its failure kind', (t) async {
    final outage = SubjectMeta.fromJson({
      'title': 'Tides',
      'goal': 'tides',
      'status': 'failed',
      'created': 1,
      'rev': 1,
      'origin': 'generated',
      'error': 'Claude is unavailable',
      'error_kind': 'claude_limit',
    });
    expect(outage.errorKind, ErrorKind.claudeLimit);
    await _pump(
      t,
      StatusGlyph(
        outage.status,
        detail: outage.error,
        errorKind: outage.errorKind,
      ),
    );
    expect(find.byIcon(errorKindIcon(ErrorKind.claudeLimit)), findsOneWidget);
    await _pump(
      t,
      const StatusGlyph(SubjectStatus.failed, errorKind: ErrorKind.modelFailed),
    );
    expect(find.byIcon(Icons.psychology_alt), findsOneWidget);
    await _pump(t, const StatusGlyph(SubjectStatus.failed));
    expect(find.byIcon(Icons.error_outline), findsOneWidget);
  });

  testWidgets('C8: a failed module shows its failure kind', (t) async {
    Module mod(String kind) => Module.fromJson({
      'id': 'a',
      'title': 'A',
      'status': 'failed',
      'error': 'why',
      'error_kind': kind,
    });
    await _pump(
      t,
      ModuleProgressTile(module: mod('claude_network'), onRetry: () {}),
    );
    expect(find.byIcon(Icons.wifi_off), findsOneWidget);
    await _pump(
      t,
      ModuleProgressTile(module: mod('too_few_cards'), onRetry: () {}),
    );
    expect(find.byIcon(Icons.filter_alt_off_outlined), findsOneWidget);
    await _pump(t, ModuleProgressTile(module: mod('new_kind'), onRetry: () {}));
    expect(find.byIcon(Icons.wifi_off), findsNothing);
    expect(find.byIcon(genericErrorIcon), findsWidgets);
  });

  testWidgets('C9: DrillFailed paints the failure glyph and still retries', (
    t,
  ) async {
    var retried = 0;
    Future<void> retry() async => retried++;
    await _pump(
      t,
      DrillFailed('model failed', retry, icon: Icons.psychology_alt),
    );
    expect(find.byIcon(Icons.psychology_alt), findsOneWidget);
    await t.tap(find.byIcon(Icons.refresh));
    expect(retried, 1);
    await _pump(t, DrillFailed('?', retry));
    expect(find.byIcon(genericErrorIcon), findsOneWidget);
  });

  testWidgets('C10: limit vs unavailable banners differ', (t) async {
    IconData shown(String? why) {
      final icon = t.widget<Icon>(
        find.descendant(
          of: find.byType(DrillBanner),
          matching: find.byType(Icon),
        ),
      );
      return icon.icon!;
    }

    await _pump(t, const DrillBanner(Unavailable(reason: 'rate_limit')));
    final limit = shown('rate_limit');
    await _pump(t, const DrillBanner(Unavailable(reason: 'network')));
    final net = shown('network');
    await _pump(t, const DrillBanner(Unavailable()));
    final none = shown(null);
    expect({limit, net, none}, hasLength(3));
    expect(none, Icons.bolt_outlined);
  });
}
