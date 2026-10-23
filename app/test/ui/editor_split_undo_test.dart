// Undo of a split in the Editor (struggle contract §2): the suspended
// original, marked `split`, shows "Split" with Restore (`card_restore` on the
// original id reverts the whole split); its live children and a child an
// earlier undo suspended (`unsplit`) offer no Restore.
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
  String? splitOf,
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
  'split_of': ?splitOf,
};

void main() {
  testWidgets('Restore a split original; its parts offer none', (t) async {
    final db = fixtureDb();
    const cards = 'tutor/v1/subjects/car/cards';
    db.root = setAt(
      db.root,
      '$cards/eng-big',
      _card(4, 'What is a piston and what does it do?', {
        'split': 1,
        'requires_of': {'eng-crank': 0},
      }, suspended: true),
    );
    db.root = setAt(
      db.root,
      '$cards/eng-big-a',
      _card(5, 'What is a piston?', {}, splitOf: 'eng-big'),
    );
    db.root = setAt(
      db.root,
      '$cards/eng-big-b',
      _card(
        6,
        'What does a piston do?',
        {'unsplit': 2},
        suspended: true,
        splitOf: 'eng-big',
      ),
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
    expect(find.textContaining('· Split'), findsOneWidget);
    expect(find.widgetWithText(TextButton, 'Restore'), findsOneWidget);
    expect(
      find.byTooltip('Undoes the split: the parts go, this card comes back'),
      findsOneWidget,
    );

    await t.tap(find.widgetWithText(TextButton, 'Restore'));
    await sent(t);
    final restore = await answer(t, db, stream, data: {'card': 'eng-big'});
    expect(restore['kind'], 'card_restore');
    expect(restore['body'], {'subject': 'car', 'card': 'eng-big'});
  });
}
