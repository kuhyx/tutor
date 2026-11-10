// build-mobile-app R7: History and a transcript fit one Pixel 6a screen; a
// long list pages (prev/next) instead of scrolling.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/history_screen.dart';
import 'package:tutor/ui/transcript_screen.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/fit.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

const _old = '20261011-090000-a1b2';

/// The fixture plus [extra] copies of an old session, and a long transcript.
FakeRtdb _db({int extra = 30, int turns = 40}) {
  final db = fixtureDb();
  final index = getAt(db.root, 'tutor/v1/session_index/$_old');
  final session = getAt(db.root, 'tutor/v1/sessions/$_old');
  for (var i = 0; i < extra; i++) {
    final sid =
        '202609${(i + 1).toString().padLeft(2, '0')}-090000-'
        '${(0xa000 + i).toRadixString(16)}';
    db.root = setAt(db.root, 'tutor/v1/sessions/$sid', session);
    if (index != null) {
      db.root = setAt(db.root, 'tutor/v1/session_index/$sid', index);
    }
  }
  db.root = setAt(db.root, 'tutor/v1/sessions/$_old/msgs', {
    for (var i = 0; i < turns; i++)
      'm${i.toString().padLeft(4, '0')}': {
        'role': i.isEven ? 'tutor' : 'user',
        'text': 'Turn $i: ${'a longer line of chat text ' * 6}',
      },
  });
  return db;
}

void main() {
  fitTest('History list pages', (t, scale) async {
    pixelView(t, scale: scale);
    final s = await fixtureServices(_db(), FakeStream());
    await pumpFit(t, HistoryScreen(services: s));
    expectFits(t, state: 'list');
    expectReachable(t, find.byKey(const ValueKey('fit-next')));
    await t.tap(find.byKey(const ValueKey('fit-next')));
    await t.pumpAndSettle();
    expectFits(t, state: 'page 2');
    expectReachable(t, find.byKey(const ValueKey('fit-prev')));
  });

  fitTest('History empty', (t, scale) async {
    pixelView(t, scale: scale);
    final db = fixtureDb();
    db.root = setAt(db.root, 'tutor/v1/sessions', null);
    db.root = setAt(db.root, 'tutor/v1/session_index', null);
    final s = await fixtureServices(db, FakeStream());
    await pumpFit(t, HistoryScreen(services: s));
    expectFits(t, state: 'empty');
  });

  fitTest('Transcript pages', (t, scale) async {
    pixelView(t, scale: scale);
    final s = await fixtureServices(_db(extra: 0), FakeStream());
    await pumpFit(t, TranscriptScreen(services: s, sid: _old));
    expectFits(t, state: 'transcript');
    expectReachable(t, controlByLabel('Repeat'));
  });
}
