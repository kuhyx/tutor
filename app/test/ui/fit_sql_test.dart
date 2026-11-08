// build-mobile-app R7: the SQL list fits one Pixel 6a screen.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/sql/sql_screen.dart';

import '../sql/sql_fixtures.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/fit.dart';
import '../support/services.dart';
import '../support/ui.dart';

/// [listData] with [n] more drills per topic, so the list must page.
Map<String, Object?> _long(int n) {
  final drills = [...listData['drills']! as List<Object?>];
  final first = drills.first! as Map<String, Object?>;
  final topics = (listData['topics'] as List<Object?>?) ?? [first['topic']];
  for (final topic in topics) {
    for (var i = 0; i < n; i++) {
      drills.add({...first, 'id': 'x-$topic-$i', 'topic': topic});
    }
  }
  return {...listData, 'drills': drills};
}

void main() {
  fitTest('SQL list pages', (t, scale) async {
    pixelView(t, scale: scale);
    final db = FakeRtdb();
    final stream = FakeStream();
    await pumpFit(
      t,
      SqlPracticeScreen(services: services(db, stream)),
      settle: false,
    );
    await answer(t, db, stream, data: _long(8));
    expectFits(t, state: 'list');
    expectReachable(t, find.byKey(const ValueKey('fit-next')));
  });

  fitTest('SQL list error', (t, scale) async {
    pixelView(t, scale: scale);
    final db = FakeRtdb();
    final stream = FakeStream();
    await pumpFit(
      t,
      SqlPracticeScreen(services: services(db, stream)),
      settle: false,
    );
    await answer(t, db, stream, code: 'model_error');
    expectFits(t, state: 'error');
  });
}
