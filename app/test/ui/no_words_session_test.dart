// textgate guard, session side: states the route sweep in no_words_test.dart
// does not reach (questions, busy + trace, card end, blocks, struggle offer,
// follow-up box, media, folded tile) paint no app words.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/card.dart';
import 'package:tutor/model/media.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/review/review_items.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/session/media.dart';
import 'package:tutor/ui/session/session_screen.dart';
import 'package:tutor/ui/struggle_offer.dart';
import 'package:tutor/ui/transcript_screen.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../../tool/fixture/fixture_trace.dart';
import '../support/composer.dart';
import '../support/fake_stream.dart';
import '../support/no_words.dart';
import '../support/ui.dart';

const _base = 'tutor/v1-e2e/sessions/$fixtureLiveSid';
const _old = '20261011-090000-a1b2';

void main() {
  for (final phone in [false, true]) {
    final where = phone ? 'phone' : 'desktop';
    testWidgets('questions with choices ($where)', (t) async {
      await openComposer(t, phone: phone);
      expectNoWords(t, 'questions ($where)');
    });
    testWidgets('comprehension check ($where)', (t) async {
      await openComposer(t, phone: phone, check: true);
      expectNoWords(t, 'check ($where)');
    });
    testWidgets('card end ($where)', (t) async {
      final (db, stream) = await openComposer(
        t,
        phone: phone,
        questions: false,
      );
      db.root = setAt(db.root, '$composeBase/meta/card_done', true);
      stream.emit(
        '$composeBase/meta',
        RtdbPut('/', getAt(db.root, '$composeBase/meta')),
      );
      await t.pumpAndSettle();
      expectNoWords(t, 'card end ($where)');
    });
  }

  testWidgets('busy turn with research steps, panels open', (t) async {
    final db = fixtureDb();
    db.root = fixtureInFlight(fixtureWithTrace(db.root), fixtureNow);
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, SessionScreen(services: s), settle: false);
    for (final path in [
      'tutor/v1-e2e/live',
      '$_base/meta',
      '$_base/msgs',
      '$_base/progress',
    ]) {
      stream.emit(path, RtdbPut('/', getAt(db.root, path)));
      await t.pump();
    }
    await t.pump(const Duration(milliseconds: 300));
    expectNoWords(t, 'busy + trace');
  });

  testWidgets('blocked: daily cap call to action', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      SessionScreen(services: s, subject: 'car', resume: true),
      settle: false,
    );
    await sent(t);
    await answer(
      t,
      db,
      stream,
      code: 'daily_new_cap',
      extra: {
        'subject_title': 'How a car works',
        'new_today': 25,
        'new_cap': 25,
        'due_in_subject': 2,
        'next': 'lift_cap',
      },
      settle: false,
    );
    expectNoWords(t, 'blocked cap');
  });

  testWidgets('past session with follow-up box and archived mark', (t) async {
    final db = fixtureDb();
    final s = await fixtureServices(db, FakeStream());
    await pumpScreen(t, TranscriptScreen(services: s, sid: _old));
    expectNoWords(t, 'transcript');
  });

  testWidgets('struggle offer, PC online and offline', (t) async {
    final s = await fixtureServices(fixtureDb(), FakeStream());
    final presence = ValueNotifier(PcPresence.online);
    const card = StudyCard(
      module: 'engine',
      order: 1,
      front: 'What does the crankshaft do?',
      back: 'Turns the pistons into rotation.',
      source: 'x',
      excerpt: 'x',
      rev: 1,
      origin: 'tutor',
    );
    await pumpScreen(
      t,
      Scaffold(
        body: StruggleOffer(
          item: const ReviewItem(
            subject: 'car',
            subjectTitle: 'How a car works',
            cardId: 'eng-crank',
            card: card,
          ),
          presence: presence,
          runner: RequestRunner(s.relay),
          onHelp: () {},
          onDismiss: () {},
        ),
      ),
    );
    expectNoWords(t, 'struggle online');
    presence.value = PcPresence.offline;
    await t.pump();
    expectNoWords(t, 'struggle offline');
  });

  testWidgets('picture and diagram attribution', (t) async {
    await pumpScreen(
      t,
      const Scaffold(
        body: Column(
          children: [
            CommonsFigure(
              Img(
                url: 'https://example.org/x.png',
                title: 'Piston',
                author: 'A. Author',
                licence: 'CC BY-SA 4.0',
                pageUrl: 'https://commons.wikimedia.org/wiki/File:X.png',
              ),
            ),
            DiagramView(Dgm(title: 'Relay', svg: 'not svg')),
          ],
        ),
      ),
    );
    expectNoWords(t, 'media');
  });
}
