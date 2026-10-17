// Golden vectors shared with the Python worker (curriculum §5):
// contract/fsrs_vectors.json at the repo root, written by
// `python -m tutor.curriculum.fsrs_vectors`.
//
// Format: [{"name", "events": [{"dev","eid","k","s","c","at","r"?,"rev"?,...}],
//           "cards": {"x": {"rev": 1}},
//           "expect": {"x": {"taught","due","stability","difficulty",
//                            "state","flagged","good","reviewed"?}},
//           "dropped": [...], "ignored": [...]}]
// Events are listed unsorted on purpose (the fold sorts). Tolerance 1e-6 on
// stability/difficulty; `due` exact to the ms; `good` (§6 unlock rule) too.
// `dropped`/`ignored` are worker-side and not checked here.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/model/log_event.dart';

File _vectors() {
  // `flutter test` runs from app/; the contract dir is the repo root's.
  final here = Directory.current.path;
  final root = here.endsWith('/app') ? Directory.current.parent.path : here;
  return File('$root/contract/fsrs_vectors.json');
}

void _check(Map<String, dynamic> v) {
  final name = v['name'] as String;
  final rows = (v['events'] as List<dynamic>).cast<Map<String, dynamic>>();
  final events = [
    for (final raw in rows)
      LoggedEvent(
        dev: raw['dev'] as String,
        eid: raw['eid'] as String,
        event: LogEvent.fromJson(raw),
      ),
  ];
  final cards = (v['cards'] as Map<String, dynamic>).map(
    (id, info) => MapEntry(
      'car/$id',
      CardInfo(rev: ((info as Map<String, dynamic>)['rev'] as num).toInt()),
    ),
  );
  final result = fold(events, cards);
  final expect_ = v['expect'] as Map<String, dynamic>;
  for (final MapEntry(key: id, value: rawWant) in expect_.entries) {
    final want = rawWant as Map<String, dynamic>;
    final key = 'car/$id';
    final card = result.scheduled[key];
    expect(card != null, want['taught'], reason: '$name: $id taught');
    expect(
      result.flagged.contains(key),
      want['flagged'],
      reason: '$name: $id flagged',
    );
    expect(
      result.good.contains(key),
      want['good'] ?? false,
      reason: '$name: $id good',
    );
    // `reviewed` (module unlock) only once the worker's vectors carry it.
    if (want.containsKey('reviewed')) {
      expect(
        result.reviewed.contains(key),
        want['reviewed'],
        reason: '$name: $id reviewed',
      );
    }
    if (card == null) continue;
    expect(
      card.due.millisecondsSinceEpoch,
      (want['due'] as num).toInt(),
      reason: '$name: $id due',
    );
    expect(
      card.stability,
      closeTo(want['stability'] as num, 1e-6),
      reason: '$name: $id stability',
    );
    expect(
      card.difficulty,
      closeTo(want['difficulty'] as num, 1e-6),
      reason: '$name: $id difficulty',
    );
    expect(card.state, want['state'], reason: '$name: $id state');
  }
}

void main() {
  final file = _vectors();
  test(
    'Dart fold matches the Python golden vectors',
    () {
      final vectors = jsonDecode(file.readAsStringSync()) as List<dynamic>;
      expect(vectors, isNotEmpty);
      for (final raw in vectors) {
        _check(raw as Map<String, dynamic>);
      }
    },
    skip: file.existsSync()
        ? false
        : 'contract/fsrs_vectors.json not produced yet (B2)',
  );
}
