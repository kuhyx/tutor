import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/review/review_session.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/util/ulid.dart';

import '../model/samples.dart';
import '../support/fake_rtdb.dart';

const _dev = '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10';
final _t0 = DateTime.utc(2026, 10);
const _ref = ModuleRef(subject: 'car', module: 'm', title: 'M');

Map<String, Object?> _in(String module, int order) => {
  ...card,
  'module': module,
  'order': order,
};

void main() {
  late EventLog events;
  late Catalog catalog;

  setUp(() async {
    final db = FakeRtdb();
    final kv = MemoryKv();
    events = EventLog(
      client: db.client(),
      kv: kv,
      dev: _dev,
      ulid: UlidGenerator(),
    );
    catalog = Catalog(client: db.client(), kv: kv);
    await kv.set(
      kCatalogCacheKey,
      jsonEncode({
        'rev': 1,
        'subjects': {
          'car': {
            'meta': subjectMeta,
            'cards': {
              'c': _in('m', 3),
              'a': _in('m', 1),
              'b': _in('m', 2),
              'flagged': _in('m', 4),
              'untaught': _in('m', 5),
              'other': _in('n', 1),
            },
          },
        },
      }),
    );
    for (final c in ['a', 'b', 'c', 'flagged', 'other']) {
      await events.record(
        TaughtEvent(subject: 'car', card: c, at: _t0.millisecondsSinceEpoch),
      );
    }
    await events.record(
      FlagEvent(
        subject: 'car',
        card: 'flagged',
        at: _t0.millisecondsSinceEpoch + 1,
        rev: 1,
        reason: 'x',
      ),
    );
  });

  test('module items: every taught card of the module, due or not', () async {
    final items = await moduleItems(
      catalog: catalog,
      events: events,
      module: _ref,
    );
    // Taught just now (nothing due), in module order; no flagged, untaught
    // or other-module cards.
    expect(items.map((i) => i.cardId), ['a', 'b', 'c']);
    expect(items.first.subjectTitle, 'How a car works');
  });

  test('requeue: Again/Hard come back at the end until Good/Easy', () async {
    final items = await moduleItems(
      catalog: catalog,
      events: events,
      module: _ref,
    );
    final run = ReviewSession(items: items, events: events, requeue: true);
    Future<void> rate(Grade g) async {
      run.reveal();
      await run.rate(g);
    }

    expect(run.left, 3);
    await rate(Grade.again); // a -> end
    expect(run.current!.cardId, 'b');
    expect(run.left, 3);
    await rate(Grade.hard); // b -> end
    await rate(Grade.good); // c done
    expect(run.current!.cardId, 'a');
    await rate(Grade.easy); // a done
    expect(run.current!.cardId, 'b');
    await rate(Grade.again); // b again
    expect(run.current!.cardId, 'b');
    await rate(Grade.good);
    expect(run.current, isNull);
    expect(run.left, 0);
    expect(run.cardsDone, 3); // distinct cards, not answers
    expect(
      (await events.all()).map((e) => e.event).whereType<ReviewEvent>(),
      hasLength(6),
    );
  });

  test('without requeue (the due queue) an Again just moves on', () async {
    final items = await moduleItems(
      catalog: catalog,
      events: events,
      module: _ref,
    );
    final run = ReviewSession(items: items, events: events);
    for (var i = 0; i < 3; i++) {
      run.reveal();
      await run.rate(Grade.again);
    }
    expect(run.current, isNull);
    expect(run.done, 3);
  });
}
