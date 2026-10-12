import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/review/review_session.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/util/ulid.dart';

import '../model/samples.dart';
import '../support/fake_rtdb.dart';

const _dev = '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10';
final _t0 = DateTime.utc(2026, 10);

void main() {
  late FakeRtdb db;
  late MemoryKv kv;
  late EventLog events;
  late Catalog catalog;

  setUp(() async {
    db = FakeRtdb();
    kv = MemoryKv();
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
            'cards': {'a': card, 'b': card},
          },
        },
      }),
    );
    for (final (c, at) in [('a', 0), ('b', 1), ('gone', 2)]) {
      await events.record(
        TaughtEvent(
          subject: 'car',
          card: c,
          at: _t0.millisecondsSinceEpoch + at,
        ),
      );
    }
  });

  test('due items across subjects; unknown cards dropped', () async {
    final items = await dueItems(
      catalog: catalog,
      events: events,
      now: _t0.add(const Duration(days: 30)),
    );
    expect(items.map((i) => i.cardId), ['a', 'b']);
    expect(items.first.subjectTitle, 'How a car works');
    expect(await dueItems(catalog: catalog, events: events, now: _t0), isEmpty);
  });

  test('reveal, rate, flag; events queued and flushed', () async {
    final items = await dueItems(
      catalog: catalog,
      events: events,
      now: _t0.add(const Duration(days: 30)),
    );
    var now = _t0.add(const Duration(days: 30));
    final run = ReviewSession(items: items, events: events, now: () => now);
    var notes = 0;
    run.addListener(() => notes++);
    await run.rate(Grade.good); // not revealed: ignored
    expect(run.done, 0);
    run
      ..reveal()
      ..reveal();
    expect(run.revealed, isTrue);
    now = now.add(const Duration(seconds: 4));
    await run.rate(Grade.good);
    expect(run.done, 1);
    expect(run.revealed, isFalse);
    db.offline = true; // flush fails: event stays queued
    await run.flag(' wrong ');
    expect(run.current, isNull);
    await run.flag('x');
    await run.rate(Grade.easy);
    run.reveal();
    expect(notes, 3);
    final all = (await events.all()).map((e) => e.event).toList();
    final review = all.whereType<ReviewEvent>().single;
    expect(review.durMs, 4000);
    expect(all.whereType<FlagEvent>().single.reason, 'wrong');
    expect(await events.pending(), 1);
    expect(ReviewSession(items: const [], events: events).current, isNull);
  });
}
