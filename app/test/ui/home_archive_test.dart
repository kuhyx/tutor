import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/home_archive.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

const _car = 'Archive How a car works';
const _undo = 'Undo archive How a car works';

/// The worker's side of an archive: the subject leaves the catalog.
void _drop(FakeRtdb db, String id) {
  db.root = setAt(db.root, 'tutor/v1-e2e/subjects/$id', null);
  db.root = setAt(db.root, 'tutor/v1-e2e/rev/catalog', 99);
}

void main() {
  testWidgets('archive icon per subject; tap archives; undo brings it back', (
    t,
  ) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, HomeScreen(services: s, onSignedOut: () {}));
    expect(glyphsLabelled(_car), findsOneWidget);
    expect(glyphsLabelled('Archive Vegetable gardening'), findsOneWidget);
    // No words: the icons carry only spoken labels.
    expect(find.textContaining('Archive'), findsNothing);

    await t.tap(glyphsLabelled(_car));
    await sent(t);
    // Hidden at once, before the PC answers; undo is offered as a glyph.
    expect(glyphsLabelled(_car), findsNothing);
    expect(glyphsLabelled(_undo), findsOneWidget);
    expect(find.textContaining('Undo'), findsNothing);
    final (_, req) = lastRequest(db);
    expect(req['kind'], 'subject_archive');
    expect(req['body'], {'subject': 'car'});
    _drop(db, 'car');
    await answer(
      t,
      db,
      stream,
      data: {'subject': 'car', 'archived': true},
      settle: false,
    );
    await sent(t);
    expect(glyphsLabelled(_car), findsNothing);

    await t.tap(glyphsLabelled(_undo));
    // The snack slides out (then a frame to drop it).
    await t.pump(const Duration(seconds: 1));
    await t.pump(const Duration(seconds: 1));
    final (_, back) = lastRequest(db);
    expect(back['kind'], 'subject_unarchive');
    expect(back['body'], {'subject': 'car'});
    expect(glyphsLabelled(_undo), findsNothing);
    // Republished by the worker.
    final car = getAt(fixtureDb().root, 'tutor/v1-e2e/subjects/car');
    db.root = setAt(db.root, 'tutor/v1-e2e/subjects/car', car);
    db.root = setAt(db.root, 'tutor/v1-e2e/rev/catalog', 100);
    await answer(t, db, stream, data: {'subject': 'car', 'archived': false});
    expect(glyphsLabelled(_car), findsOneWidget);
  });

  testWidgets('the undo glyph goes away after a few seconds', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, HomeScreen(services: s, onSignedOut: () {}));
    await t.tap(glyphsLabelled(_car));
    await sent(t);
    expect(glyphsLabelled(_undo), findsOneWidget);
    // Shown in (entrance), then the timer runs, then it slides out.
    await t.pump(const Duration(seconds: 1));
    await t.pump(undoArchiveFor);
    await t.pump(const Duration(seconds: 1));
    expect(glyphsLabelled(_undo), findsNothing);
  });

  testWidgets('a refused archive shows the subject again with an error cue', (
    t,
  ) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, HomeScreen(services: s, onSignedOut: () {}));
    await t.tap(glyphsLabelled(_car));
    await sent(t);
    expect(glyphsLabelled(_car), findsNothing);
    await answer(t, db, stream, code: 'bad_request', settle: false);
    await sent(t);
    expect(glyphsLabelled(_car), findsOneWidget);
    expect(cueOfKind(CueKind.error), findsOneWidget);
  });

  testWidgets('phone: the archive glyph is in the subject sheet', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      HomeScreen(services: s, onSignedOut: () {}),
      size: const Size(411, 860),
    );
    await t.longPress(find.byKey(const ValueKey('subject-tile-car')));
    await t.pumpAndSettle();
    await t.tap(glyphsLabelled(_car));
    await sent(t);
    expect(lastRequest(db).$2['kind'], 'subject_archive');
    expect(find.byKey(const ValueKey('subject-tile-car')), findsNothing);
    expect(glyphsLabelled(_undo), findsOneWidget);
  });
}
