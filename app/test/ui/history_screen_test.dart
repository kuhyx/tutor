import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/history_screen.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

const _old = 'tutor/v1/sessions/20261011-090000-a1b2';

void main() {
  testWidgets('list, archived toggle, transcript actions', (t) async {
    final db = fixtureDb();
    db.root = setAt(db.root, '$_old/msgs', {
      'm0001': {'role': 'tutor', 'text': 'Earlier **turn**'},
    });
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, HistoryScreen(services: s));
    expect(find.textContaining('2026-10-11 09:00'), findsOneWidget);
    expect(find.textContaining('2026-10-10'), findsNothing);
    await t.tap(controlByLabel('Show archived (1)'));
    await t.pumpAndSettle();
    expect(bySpoken('archived: no reply'), findsWidgets);
    await t.tap(controlByLabel('Hide archived (1)'));
    await t.pumpAndSettle();

    await t.tap(find.textContaining('2026-10-11 09:00'));
    await t.pumpAndSettle();
    expect(bySpoken('Read-only'), findsOneWidget);
    expect(find.text('a1b2'), findsOneWidget); // the id chip
    expect(find.textContaining('Earlier'), findsOneWidget);
    await t.tap(controlByLabel('Archive'));
    await t.pumpAndSettle();
    expect(getAt(db.root, '$_old/user/archived'), isTrue);
    expect(controlByLabel('Unarchive'), findsOneWidget);

    await t.tap(find.byType(CheckboxListTile));
    await sent(t);
    final mark = await answer(t, db, stream);
    expect(mark['body'], {
      'subject': 'car',
      'card': 'eng-crank',
      'done': false,
    });

    await t.tap(controlByLabel('Repeat'));
    await sent(t);
    final repeat = await answer(
      t,
      db,
      stream,
      data: {'session': 'x'},
      settle: false,
    );
    expect(repeat['body'], {
      'subject': 'car',
      'card': 'eng-crank',
      'device': 'desktop',
    });
    expect(bySpoken('Target card'), findsWidgets); // replaced by Session
  });

  testWidgets('empty and unreachable', (t) async {
    final db = fixtureDb();
    db.root = setAt(db.root, 'tutor/v1/session_index', null);
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, HistoryScreen(services: s));
    expect(bySpoken('No past sessions'), findsOneWidget);
    db.offline = true;
    await t.tap(controlByLabel('Reload'));
    await t.pumpAndSettle();
    expect(cueOfKind(CueKind.error), findsOneWidget);
  });
}
