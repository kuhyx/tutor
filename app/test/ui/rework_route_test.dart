// `/rework/<subject>/<module>/<slug>`, the LeetCode lock's `?` on a problem:
// the route opens the rework chat, a turn shows the reply and its cards.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/coach/rework_requests.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/coach/rework_screen.dart';
import 'package:tutor/ui/deep_link.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/ui.dart';

const _lc = 'leetcode-easy-algorithms-in-typescript';
const _card = {
  'id': 'a-map',
  'front': 'Which lookup is O(1)?',
  'back': 'A map.',
};

Map<String, Object?> _opened({List<Object?> thread = const []}) => {
  'rework_id': 'abcdef012345',
  'subject': _lc,
  'module': 'hashing',
  'module_title': 'Hashing',
  'slug': 'two-sum',
  'thread': thread,
  'cards': const <Object?>[],
  'history': const {'submissions': 2, 'days': 1, 'sessions': 0},
};

void main() {
  test('an open window takes /learn and /rework offers, nothing else', () {
    expect(handedOffer('learn /learn/car/fuel'), isTrue);
    expect(handedOffer('learn /rework/$_lc/hashing/two-sum'), isTrue);
    expect(handedOffer('learn /focus'), isFalse);
    expect(handedOffer('took /rework/x/y/z'), isFalse);
  });

  test('a bad result is a FormatException', () {
    expect(
      () => parseReworkOpened({'rework_id': 1}),
      throwsA(isA<FormatException>()),
    );
    expect(
      parseReworkOpened({..._opened(), 'module_title': null}).moduleTitle,
      'hashing',
    );
  });

  Future<(FakeRtdb, FakeStream)> route(WidgetTester t, String path) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    late BuildContext ctx;
    await pumpScreen(
      t,
      Builder(
        builder: (context) {
          ctx = context;
          return const SizedBox();
        },
      ),
    );
    final opening = openRoute(ctx, s, path);
    await sent(t);
    expect(opening, isNotNull);
    return (db, stream);
  }

  testWidgets('the route opens the chat; a turn adds cards', (t) async {
    final (db, stream) = await route(t, '/rework/$_lc/hashing/two-sum');
    expect(find.byType(ReworkScreen), findsOneWidget);
    final (_, open) = lastRequest(db);
    expect(open['kind'], 'rework_open');
    expect(open['body'], {
      'subject': _lc,
      'module': 'hashing',
      'slug': 'two-sum',
    });
    final old = {'mine': true, 'md': 'Earlier.'};
    await answer(t, db, stream, data: _opened(thread: [old]));
    expect(find.text('Hashing'), findsOneWidget);
    expect(find.text('Earlier.'), findsOneWidget);
    await t.enterText(find.byKey(const ValueKey('answer')), 'Why a map?');
    await t.pump();
    await t.tap(find.byKey(const ValueKey('send')));
    await sent(t);
    final (_, turn) = lastRequest(db);
    expect(turn['kind'], 'rework_turn');
    expect(turn['body'], {'rework_id': 'abcdef012345', 'text': 'Why a map?'});
    expect(find.text('Why a map?'), findsOneWidget);
    await answer(
      t,
      db,
      stream,
      data: {
        'reply_md': 'A map finds it.',
        'cards': [_card],
        'added': 1,
      },
    );
    expect(find.text('A map finds it.'), findsOneWidget);
    expect(find.text('Which lookup is O(1)?'), findsOneWidget);
    expect(find.text('1'), findsOneWidget); // the cards badge
  });

  testWidgets('an empty reply adds no bubble; a bad one shows the cue', (
    t,
  ) async {
    final (db, stream) = await route(t, '/rework/$_lc/hashing/two-sum');
    await answer(t, db, stream, data: _opened());
    await t.enterText(find.byKey(const ValueKey('answer')), 'Lost.');
    await t.pump();
    await t.tap(find.byKey(const ValueKey('send')));
    await sent(t);
    await answer(t, db, stream, data: {'reply_md': '', 'cards': <Object?>[]});
    expect(find.byType(ListTile), findsNothing);
    await t.enterText(find.byKey(const ValueKey('answer')), 'Again.');
    await t.pump();
    await t.tap(find.byKey(const ValueKey('send')));
    await sent(t);
    await answer(t, db, stream, data: {'cards': 'nope'});
    expect(find.byType(CueChip), findsOneWidget);
  });

  testWidgets('a short /rework route opens nothing', (t) async {
    final (db, _) = await route(t, '/rework/$_lc/hashing');
    expect(find.byType(ReworkScreen), findsNothing);
    expect(getAt(db.root, 'tutor/v1-e2e/requests'), isNull);
  });
}
