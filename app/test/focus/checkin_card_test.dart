import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/focus/checkin_card.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/util/ulid.dart';

import '../model/samples.dart';
import '../support/fake_rtdb.dart';

const _dev = '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10';
final _t0 = DateTime.utc(2026, 10);
const _day = Duration(days: 1);

void main() {
  late EventLog events;
  late Catalog catalog;

  Future<String?> pickAt(List<String> subjects, DateTime now) async {
    final item = await pickCheckinCard(
      catalog: catalog,
      events: events,
      subjects: subjects,
      now: now,
    );
    return item == null ? null : '${item.subject}/${item.cardId}';
  }

  Future<void> taught(String s, String c, Duration after) => events.record(
    TaughtEvent(subject: s, card: c, at: _t0.add(after).millisecondsSinceEpoch),
  );

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
            'cards': {'a': card, 'b': card, 'new': card},
          },
          'garden': {
            'meta': subjectMeta,
            'cards': {'g': card},
          },
        },
      }),
    );
    await taught('car', 'a', const Duration(hours: 2));
    await taught('car', 'b', Duration.zero); // falls due first
    await taught('garden', 'g', -_day * 9); // most overdue, other subject
  });

  test("the most overdue taught card of the project's subjects", () async {
    expect(await pickAt(['car'], _t0.add(_day * 30)), 'car/b');
    expect(await pickAt(['car', 'garden'], _t0.add(_day * 30)), 'garden/g');
  });

  test('none due: the soonest due; never an untaught card', () async {
    expect(await pickAt(['car'], _t0), 'car/b');
  });

  test('no subjects, or no taught card: none (the old tap)', () async {
    expect(await pickAt([], _t0.add(_day * 30)), isNull);
    expect(await pickAt(['nothing'], _t0.add(_day * 30)), isNull);
  });

  test('a flagged card is skipped', () async {
    await events.record(
      FlagEvent(
        subject: 'car',
        card: 'b',
        at: _t0.add(_day).millisecondsSinceEpoch,
        rev: 1,
        reason: 'x',
      ),
    );
    expect(await pickAt(['car'], _t0.add(_day * 30)), 'car/a');
  });
}
