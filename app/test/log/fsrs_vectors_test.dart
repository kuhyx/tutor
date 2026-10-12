// Golden vectors shared with the Python worker (curriculum §5): B2 writes
// contract/fsrs_vectors.json at the repo root; until it exists this test is
// skipped, not passed.
//
// Format: [{"events":[["taught",at],["review",at,3],...],
//           "expect":{"due":ms,"stability":x,"difficulty":y,"state":"review"}}]
// Tolerance 1e-6 on stability/difficulty; `due` exact to the second.
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

LogEvent _event(List<dynamic> row) {
  final at = (row[1] as num).toInt();
  return switch (row[0]) {
    'taught' => TaughtEvent(subject: 'v', card: 'c', at: at),
    'untaught' => UntaughtEvent(subject: 'v', card: 'c', at: at),
    'review' => ReviewEvent(
      subject: 'v',
      card: 'c',
      at: at,
      grade: Grade.parse((row[2] as num).toInt()),
      rev: 1,
    ),
    final k => throw FormatException('unknown vector event $k'),
  };
}

void main() {
  final file = _vectors();
  test(
    'Dart fold matches the Python golden vectors',
    () {
      final vectors = jsonDecode(file.readAsStringSync()) as List<dynamic>;
      expect(vectors, isNotEmpty);
      for (final (i, raw) in vectors.indexed) {
        final v = raw as Map<String, dynamic>;
        final rows = (v['events'] as List<dynamic>).cast<List<dynamic>>();
        final events = [
          for (final (n, row) in rows.indexed)
            LoggedEvent(
              dev: 'd',
              eid: n.toString().padLeft(8, '0'),
              event: _event(row),
            ),
        ];
        final want = v['expect'] as Map<String, dynamic>;
        final card = fold(events, const {
          'v/c': CardInfo(rev: 1),
        }).scheduled['v/c'];
        expect(card, isNotNull, reason: 'vector $i');
        expect(
          card!.due.millisecondsSinceEpoch ~/ 1000,
          (want['due'] as num).toInt() ~/ 1000,
          reason: 'vector $i due',
        );
        expect(card.stability, closeTo(want['stability'] as num, 1e-6));
        expect(card.difficulty, closeTo(want['difficulty'] as num, 1e-6));
        expect(card.state, want['state'], reason: 'vector $i state');
      }
    },
    skip: file.existsSync()
        ? false
        : 'contract/fsrs_vectors.json not produced yet (B2)',
  );
}
