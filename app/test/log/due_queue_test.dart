// The due queue (`reviewQueue`) against contract/due_queue_vectors.json, the
// file the worker's `no_card.due_now` runs too (tutor/tests/
// test_due_queue_vectors.py): taught, not flagged at the current rev, not
// suspended, `due <= now`. The signed review_due.json and the route
// `/review/<subject>/<module>` therefore name the same cards.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/model/log_event.dart';

List<Map<String, dynamic>> _cases() {
  // `flutter test` runs from app/; the contract dir is the repo root's.
  final here = Directory.current.path;
  final root = here.endsWith('/app') ? Directory.current.parent.path : here;
  final raw = File('$root/contract/due_queue_vectors.json').readAsStringSync();
  return (jsonDecode(raw) as List<dynamic>).cast<Map<String, dynamic>>();
}

void main() {
  for (final c in _cases()) {
    test(c['name'] as String, () {
      final events = [
        for (final raw
            in (c['events'] as List<dynamic>).cast<Map<String, dynamic>>())
          LoggedEvent(
            dev: raw['dev'] as String,
            eid: raw['eid'] as String,
            event: LogEvent.fromJson(raw),
          ),
      ];
      final infos = {
        for (final MapEntry(:key, :value)
            in (c['cards'] as Map<String, dynamic>).entries)
          'car/$key': CardInfo(
            rev: ((value as Map<String, dynamic>)['rev'] as num).toInt(),
            suspended: value['suspended'] as bool,
          ),
      };
      final folded = fold(events, infos);
      for (final check
          in (c['checks'] as List<dynamic>).cast<Map<String, dynamic>>()) {
        final now = DateTime.fromMillisecondsSinceEpoch(
          (check['now'] as num).toInt(),
          isUtc: true,
        );
        final due = [
          for (final d in reviewQueue(folded, infos, now))
            d.key.substring('car/'.length),
        ]..sort();
        expect(due, (check['due'] as List<dynamic>).cast<String>()..sort());
      }
    });
  }
}
