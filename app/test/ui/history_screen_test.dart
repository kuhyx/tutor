import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/history_screen.dart';

import '../support/fake_stream.dart';
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
    await t.tap(find.text('Show archived (1)'));
    await t.pumpAndSettle();
    expect(find.text('archived: no reply'), findsOneWidget);
    await t.tap(find.text('Hide archived (1)'));
    await t.pumpAndSettle();

    await t.tap(find.textContaining('2026-10-11 09:00'));
    await t.pumpAndSettle();
    expect(find.textContaining('read-only'), findsOneWidget);
    expect(find.textContaining('Earlier'), findsOneWidget);
    await t.tap(find.text('Archive'));
    await t.pumpAndSettle();
    expect(getAt(db.root, '$_old/user/archived'), isTrue);
    expect(find.text('Unarchive'), findsOneWidget);

    await t.tap(find.byType(CheckboxListTile));
    await sent(t);
    final mark = await answer(t, db, stream);
    expect(mark['body'], {
      'subject': 'car',
      'card': 'eng-crank',
      'done': false,
    });

    await t.tap(find.text('Repeat'));
    await sent(t);
    final repeat = await answer(
      t,
      db,
      stream,
      data: {'session': 'x'},
      settle: false,
    );
    expect(repeat['body'], {'subject': 'car', 'card': 'eng-crank'});
    expect(find.text('Target card'), findsOneWidget); // replaced by Session
  });

  testWidgets('empty and unreachable', (t) async {
    final db = fixtureDb();
    db.root = setAt(db.root, 'tutor/v1/session_index', null);
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, HistoryScreen(services: s));
    expect(find.text('No past sessions'), findsOneWidget);
    db.offline = true;
    await t.tap(find.byTooltip('Reload'));
    await t.pumpAndSettle();
    expect(find.textContaining('Could not load'), findsOneWidget);
  });
}
