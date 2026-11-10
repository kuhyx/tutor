// The result `kind` (DOCS-relay-kinds.md): every kind and phase the worker
// can send has its own glyph, checked against contract/relay_kinds.json
// (written by scripts/gen_relay_kinds.py); an old result without `kind`
// gets the same kind from its code; the cue never speaks the worker's
// sentence; no_card_left draws its due time and module without words.
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/progress/terms.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/ui/learn_bits.dart';
import 'package:tutor/ui/relay_cue.dart';
import 'package:tutor/ui/session/blocked_panel.dart';
import 'package:tutor/ui/session/session_screen.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

Map<String, dynamic> _golden() {
  // `flutter test` runs from app/; the contract dir is the repo root's.
  final here = Directory.current.path;
  final root = here.endsWith('/app') ? Directory.current.parent.path : here;
  final file = File('$root/contract/relay_kinds.json');
  return jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
}

final List<Map<String, dynamic>> _cases = (_golden()['cases'] as List<dynamic>)
    .cast<Map<String, dynamic>>();
final List<String> _phases = (_golden()['phases'] as List<dynamic>)
    .cast<String>();
const _sentinel = 'SERVER-SENTENCE-7f3a';

RelayFailed _failed(Map<String, Object?> result) => statusOf({
  'result': {'ok': false, 'at': 1, ...result},
}) as RelayFailed;

/// The golden row as an old server sends it: no `kind`.
Map<String, Object?> _oldNode(Map<String, dynamic> row) => {
  'code': row['code'],
  'error': _sentinel,
  if (row['reason'] != null) 'reason': row['reason'],
  if (row['next'] != null) 'next': row['next'],
  if (row['next'] == 'review_module') 'module': 'fuel',
  if (row['next'] == 'reviews_due') 'due_at': 1,
};

Future<(FakeRtdb, FakeStream)> _blocked(
  WidgetTester t,
  String code,
  Map<String, Object?> extra,
) async {
  final db = fixtureDb();
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
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
    error: _sentinel,
    extra: extra,
    settle: false,
  );
  await sent(t);
  return (db, stream);
}

/// Everything painted inside the block's cue, letters and digits only.
String _paintedInCue(WidgetTester t) {
  final cue = find.descendant(
    of: find.byType(BlockedPanel),
    matching: find.byType(CueChip),
  );
  return t
      .widgetList<RichText>(
        find.descendant(of: cue, matching: find.byType(RichText)),
      )
      .map((r) => r.text.toPlainText())
      .join()
      .replaceAll(RegExp(r'[^\p{L}\p{N}]', unicode: true), '');
}

void main() {
  test('every golden kind has its own, non-fallback glyph', () {
    final kinds = {for (final r in _cases) r['kind'] as String};
    expect(kinds, isNotEmpty);
    final glyphs = {for (final k in kinds) kindIcon(k)};
    expect(glyphs, hasLength(kinds.length), reason: 'glyphs repeat');
    expect(glyphs, isNot(contains(fallbackErrorIcon)));
    expect(glyphs, isNot(contains(workingIcon)));
    expect(kindIcon('err_from_the_future'), fallbackErrorIcon);
    expect(kindIcon(null), fallbackErrorIcon);
    expect(kindIcons.keys.toSet(), kinds, reason: 'app has a stale kind');
  });

  test('every golden phase parses and has its own glyph', () {
    final phases = [for (final p in _phases) Phase.parse(p)];
    expect(phases, isNot(contains(Phase.unknown)));
    final glyphs = {for (final p in phases) phaseIcon(p)};
    expect(glyphs, hasLength(_phases.length));
    expect(glyphs, isNot(contains(workingIcon)));
    expect(Phase.parse('reticulating'), Phase.unknown);
    expect(phaseIcon(Phase.unknown), workingIcon);
  });

  test('an old result without kind gets the golden kind from its code', () {
    for (final row in _cases) {
      expect(_failed(_oldNode(row)).kind, row['kind'], reason: '$row');
    }
    expect(_failed({'code': 'weird'}).kind, isNull);
  });

  test('a sent kind wins; the label is the app sentence per kind', () {
    for (final row in _cases) {
      final f = _failed({..._oldNode(row), 'kind': row['kind']});
      expect(f.kind, row['kind']);
      expect(f.text, isNot(contains(_sentinel)), reason: '$row');
      expect(relayCue(f)!.semanticLabel, isNot(contains(_sentinel)));
      expect(relayCue(f)!.icon, failureIcon(f));
    }
    final future = _failed({'code': 'model_error', 'kind': 'err_new_thing'});
    expect(relayCue(future)!.icon, fallbackErrorIcon);
    expect(relayCue(future)!.kind, CueKind.error);
  });

  test('blocks and the paste refusal are calm; failures are red', () {
    for (final row in _cases) {
      final kind = row['kind'] as String;
      final calm = kind.startsWith('blocked_') || kind.startsWith('refused_');
      expect(kindIsCalm(kind), calm, reason: kind);
    }
  });

  test('an unknown phase is the working glyph beside the spinner', () {
    final s = statusOf({
      'claim': {
        'by': 'pc',
        'lease_until': 1,
        'attempt': 1,
        'phase': 'zzz',
        'at': 1,
      },
    });
    expect(s, isA<RelayWorking>());
    final cue = relayCue(s)!;
    expect(cue.icon, workingIcon);
    expect(cue.kind, CueKind.pending);
  });

  test('the ring is time left over 24 h: full, partial, empty', () {
    final now = DateTime.fromMillisecondsSinceEpoch(fixtureNow);
    int at(Duration d) => fixtureNow + d.inMilliseconds;
    expect(DueRing(at(const Duration(hours: 30))).fillAt(now), 1);
    expect(DueRing(at(const Duration(hours: 6))).fillAt(now), 0.25);
    expect(DueRing(at(-const Duration(hours: 1))).fillAt(now), 0);
  });

  testWidgets('the ring redraws on its minute tick and stops on dispose', (
    t,
  ) async {
    var clock = DateTime.fromMillisecondsSinceEpoch(fixtureNow);
    final due = fixtureNow + const Duration(hours: 12).inMilliseconds;
    await t.pumpWidget(MaterialApp(home: DueRing(due, now: () => clock)));
    double fill() => t
        .widget<CircularProgressIndicator>(
          find.byType(CircularProgressIndicator),
        )
        .value!;
    expect(fill(), 0.5);
    clock = clock.add(const Duration(hours: 6));
    await t.pump(const Duration(minutes: 1));
    expect(fill(), 0.25);
    await t.pumpWidget(const SizedBox());
  });

  testWidgets('no_card_left due: clock glyph plus a ring, no text', (t) async {
    final due = fixtureNow + const Duration(hours: 6).inMilliseconds;
    await _blocked(t, 'no_card_left', {
      'subject_title': 'How a car works',
      'next': 'reviews_due',
      'due_at': due,
    });
    expect(find.byIcon(Icons.schedule), findsOneWidget);
    final ring = t.widget<DueRing>(find.byType(DueRing));
    expect(ring.dueAt, due);
    expect(
      find.descendant(
        of: find.byType(BlockedPanel),
        matching: find.byType(Text),
      ),
      findsNothing,
    );
    expect(_paintedInCue(t), isEmpty);
    expect(cueLabelled('No card left', prefix: true), findsOneWidget);
    expect(cueLabelled(_sentinel, prefix: true), findsNothing);
  });

  testWidgets('no_card_left review: the module mark, tappable', (t) async {
    await _blocked(t, 'no_card_left', {
      'subject_title': 'How a car works',
      'next': 'review_module',
      'module': 'fuel',
      'module_title': 'Fuel and ignition',
    });
    final cue = find.descendant(
      of: find.byType(BlockedPanel),
      matching: find.byType(CueChip),
    );
    final mark = find.descendant(
      of: cue,
      matching: find.byType(ModuleMarkIcon),
    );
    expect(mark, findsOneWidget);
    expect(t.widget<ModuleMarkIcon>(mark).mark, ModuleMark.done);
    expect(_paintedInCue(t), isEmpty);
    await t.tap(mark);
    await sent(t);
    await sent(t);
    expect(controlByLabel('Review: Fuel and ignition'), findsOneWidget);
  });

  testWidgets('locked review: tapping the replay glyph opens the review', (
    t,
  ) async {
    await _blocked(t, 'locked', {
      'subject_title': 'How a car works',
      'next': 'review_module',
      'module': 'fuel',
      'module_title': 'Fuel and ignition',
    });
    expect(find.byIcon(Icons.replay), findsOneWidget);
    expect(_paintedInCue(t), isEmpty);
    await t.tap(find.byIcon(Icons.replay));
    await sent(t);
    await sent(t);
    expect(controlByLabel('Review: Fuel and ignition'), findsOneWidget);
  });

  testWidgets('a red failure speaks the app sentence, never the worker', (
    t,
  ) async {
    await _blocked(t, 'model_error', const {});
    expect(find.byIcon(kindIcon('err_model')), findsOneWidget);
    expect(cueOfKind(CueKind.error), findsOneWidget);
    final semantics = t.ensureSemantics();
    expect(find.bySemanticsLabel(RegExp(_sentinel)), findsNothing);
    semantics.dispose();
  });
}
