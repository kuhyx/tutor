// The result `kind` (DOCS-relay-kinds.md): every kind and phase the worker
// can send has its own glyph, checked against contract/relay_kinds.json
// (written by scripts/gen_relay_kinds.py); an old result without `kind`
// gets the same kind from its code; the cue never speaks the worker's
// sentence (the blocked panel's drawing: relay_blocked_panel_test.dart).
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/ui/relay_cue.dart';
import 'package:tutor/widgets/cue_chip.dart';

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
}
