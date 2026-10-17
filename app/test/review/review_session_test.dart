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
          'garden': {
            'meta': {...subjectMeta, 'title': 'Gardening'},
            'cards': {'g': card},
          },
        },
      }),
    );
    for (final (subject, c, at) in [
      ('car', 'a', 0),
      ('car', 'b', 1),
      ('car', 'gone', 2),
      ('garden', 'g', 3),
    ]) {
      await events.record(
        TaughtEvent(
          subject: subject,
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
    expect(items.map((i) => i.cardId), ['a', 'b', 'g']);
    expect(items.first.subjectTitle, 'How a car works');
    expect(await dueItems(catalog: catalog, events: events, now: _t0), isEmpty);
  });

  test("a subject filter keeps only that subject's due cards", () async {
    final later = _t0.add(const Duration(days: 30));
    Future<List<String>> keys(String? subject) async => [
      for (final i in await dueItems(
        catalog: catalog,
        events: events,
        now: later,
        subject: subject,
      ))
        '${i.subject}/${i.cardId}',
    ];
    expect(await keys('car'), ['car/a', 'car/b']);
    expect(await keys('garden'), ['garden/g']);
    expect(await keys('nope'), isEmpty);
    expect(await keys(null), hasLength(3));
  });

  test('reveal, rate, flag; events queued and flushed', () async {
    final items = await dueItems(
      catalog: catalog,
      events: events,
      now: _t0.add(const Duration(days: 30)),
      subject: 'car',
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

  test('Back re-shows the last rated card; re-rating replaces it', () async {
    final items = await dueItems(
      catalog: catalog,
      events: events,
      now: _t0.add(const Duration(days: 30)),
      subject: 'car',
    );
    final run = ReviewSession(items: items, events: events)..reveal();
    await run.rate(Grade.good); // a
    run.reveal();
    await run.rate(Grade.easy); // b
    expect(run.current, isNull);
    await run.back();
    expect((run.current!.cardId, run.revealed), ('b', true));
    expect(run.undoneGrade, Grade.easy);
    await run.back();
    expect(run.current!.cardId, 'a');
    expect(run.undoneGrade, Grade.good);
    expect(run.canBack, isFalse);
    await run.back(); // nothing before: no-op
    expect(run.current!.cardId, 'a');
    await run.rate(Grade.again);
    expect(run.undoneGrade, isNull);
    expect(run.current!.cardId, 'b');
    final all = await events.all();
    final reviews = {
      for (final e in all)
        if (e.event is ReviewEvent) e.eid: e,
    };
    final undone = [
      for (final e in all)
        if (e.event case ReviewUndoEvent(:final of)) of,
    ];
    expect(undone, hasLength(2));
    expect(undone.every(reviews.containsKey), isTrue);
    // A flag cannot be undone, so Back never steps across one.
    await run.flag('x');
    expect(run.canBack, isFalse);
  });
}
