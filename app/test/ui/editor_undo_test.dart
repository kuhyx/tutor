// Undo of card edits in the Editor: a card the tutor removed shows "Removed
// by tutor" with Restore (`card_restore`); a card the Editor removed shows
// "Removed" with Restore too (older ones, with no record, say Restore only
// un-suspends); a card the tutor added can be removed (`card_remove`,
// suspended, never deleted).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/editor_screen.dart';

import '../support/fake_stream.dart';
import '../support/ui.dart';

Map<String, Object?> _card(
  int order,
  String front,
  Map<String, Object?> tutor, {
  bool suspended = false,
}) => {
  'module': 'engine',
  'order': order,
  'front': front,
  'back': 'An answer.',
  'source': 'https://en.wikipedia.org/wiki/Piston',
  'excerpt': 'a piston is a moving part that slides in a cylinder',
  'rev': 1,
  'origin': 'edited',
  'suspended': suspended,
  'tutor': tutor,
};

void main() {
  testWidgets('Restore a tutor-removed card; Remove a tutor-added one', (
    t,
  ) async {
    final db = fixtureDb();
    const cards = 'tutor/v1/subjects/car/cards';
    db.root = setAt(
      db.root,
      '$cards/eng-old',
      _card(4, 'What is a piston?', {
        'removed': 1,
        'requires_of': {'eng-crank': 0},
      }, suspended: true),
    );
    db.root = setAt(
      db.root,
      '$cards/eng-new',
      _card(5, 'What does a piston do?', {'added': 1}),
    );
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      EditorScreen(services: s, subject: 'car'),
      size: const Size(800, 1600),
    );
    await t.tap(find.text('The four-stroke engine'));
    await t.pumpAndSettle();
    expect(find.textContaining('Removed by tutor'), findsOneWidget);
    // Only tutor-added, live cards get Remove; only tutor-removed get Restore.
    expect(find.byTooltip('Remove'), findsOneWidget);
    expect(find.widgetWithText(TextButton, 'Restore'), findsOneWidget);

    await t.tap(find.widgetWithText(TextButton, 'Restore'));
    await sent(t);
    final restore = await answer(t, db, stream, data: {'card': 'eng-old'});
    expect(restore['kind'], 'card_restore');
    expect(restore['body'], {'subject': 'car', 'card': 'eng-old'});

    await t.tap(find.byTooltip('Remove'));
    await sent(t);
    final remove = await answer(t, db, stream, data: {'card': 'eng-new'});
    expect(remove['kind'], 'card_remove');
    expect(remove['body'], {'subject': 'car', 'card': 'eng-new'});
  });

  testWidgets('Restore a card the Editor removed, with or without a record', (
    t,
  ) async {
    final db = fixtureDb();
    const cards = 'tutor/v1/subjects/car/cards';
    db.root = setAt(
      db.root,
      '$cards/eng-mine',
      _card(4, 'What is a piston?', {
        'added': 1,
        'editor_removed': 2,
        'requires_of': {'eng-crank': 0},
      }, suspended: true),
    );
    db.root = setAt(
      db.root,
      '$cards/eng-old',
      _card(5, 'What does a piston do?', {'added': 1}, suspended: true),
    );
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      EditorScreen(services: s, subject: 'car'),
      size: const Size(800, 1600),
    );
    await t.tap(find.text('The four-stroke engine'));
    await t.pumpAndSettle();
    expect(find.textContaining('Removed by tutor'), findsNothing);
    expect(find.textContaining('· Removed'), findsNWidgets(2));
    expect(find.widgetWithText(TextButton, 'Restore'), findsNWidgets(2));
    expect(
      find.byTooltip('Puts the card and its prerequisites back'),
      findsOneWidget,
    );
    expect(
      find.byTooltip(
        'Removed before the Editor kept a record: only un-suspends it, '
        'prerequisites are not restored',
      ),
      findsOneWidget,
    );

    await t.tap(find.widgetWithText(TextButton, 'Restore').first);
    await sent(t);
    final restore = await answer(t, db, stream, data: {'card': 'eng-mine'});
    expect(restore['kind'], 'card_restore');
    expect(restore['body'], {'subject': 'car', 'card': 'eng-mine'});
  });
}
