// The review lists behind the module gate (kuhy, 2026-11-22): a module
// review shows only the cards not yet passed (a Good one never comes back,
// the image-2 bug), the gate review shows the worker's `gate_cards` minus
// any the newest log shows passed, and both pull the log first, so a card
// taught on another device minutes ago is in.
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/review/review_items.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/util/ulid.dart';

import '../model/samples.dart';
import '../support/fake_rtdb.dart';

const _dev = '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10';
const _pc = '9c1d2e3f-4a5b-4c6d-8e7f-0a1b2c3d4e5f';
final _t0 = DateTime.utc(2026, 10);
const _ref = ModuleRef(subject: 'car', module: 'm', title: 'M');

Map<String, Object?> _in(String module, int order) => {
  ...card,
  'module': module,
  'order': order,
};

void main() {
  late FakeRtdb db;
  late EventLog events;
  late Catalog catalog;

  Future<void> rate(String c, Grade g, {int at = 1000}) => events.record(
    ReviewEvent(
      subject: 'car',
      card: c,
      grade: g,
      at: _t0.millisecondsSinceEpoch + at,
      rev: 1,
    ),
  );

  setUp(() async {
    db = FakeRtdb();
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
              'a': _in('m', 1),
              'b': _in('m', 2),
              'c': _in('m', 3),
              'other': _in('n', 1),
            },
          },
        },
      }),
    );
    // Taught by the PC worker (a review by the device that teaches is a
    // drill pick and never passes a card).
    var n = 0;
    db.root = setAt(null, 'tutor/v1-e2e/log', {
      _pc: {
        for (final c in ['a', 'b', 'c', 'other'])
          '01JA000000000000000000000${n++}': {
            'k': 'taught',
            's': 'car',
            'c': c,
            'at': _t0.millisecondsSinceEpoch,
          },
      },
    });
  });

  test(
    'module review: a card rated Good since taught never comes back',
    () async {
      await rate('b', Grade.good);
      await rate('c', Grade.hard); // Hard does not pass
      final items = await moduleItems(
        catalog: catalog,
        events: events,
        module: _ref,
      );
      expect(items.map((i) => i.cardId), ['a', 'c']);
    },
  );

  test('gate review: the worker cards minus the ones passed since', () async {
    await rate('a', Grade.easy);
    final items = await gateItems(
      catalog: catalog,
      events: events,
      subject: 'car',
      cards: const ['c', 'a', 'other', 'gone'],
      now: _t0.add(const Duration(minutes: 5)),
    );
    // Worker order kept; a passed; an unknown card dropped.
    expect(items.map((i) => i.cardId), ['c', 'other']);
  });

  test('gate review: a passed card that is due stays in', () async {
    await rate('a', Grade.good);
    final items = await gateItems(
      catalog: catalog,
      events: events,
      subject: 'car',
      cards: const ['a'],
      now: _t0.add(const Duration(days: 400)),
    );
    expect(items.map((i) => i.cardId), ['a']);
  });

  test('both pull first: a card taught on the PC a minute ago is in', () async {
    db.root = setAt(
      db.root,
      'tutor/v1-e2e/log/$_pc/01JA0000000000000000000009',
      {
        'k': 'taught',
        's': 'car',
        'c': 'fresh',
        'at': _t0.millisecondsSinceEpoch + 60000,
      },
    );
    final s = jsonDecode((await catalog.kv.get(kCatalogCacheKey))!) as Map;
    ((s['subjects'] as Map)['car'] as Map)['cards'] = {
      ...((s['subjects'] as Map)['car'] as Map)['cards'] as Map,
      'fresh': _in('m', 4),
    };
    await catalog.kv.set(kCatalogCacheKey, jsonEncode(s));
    final module = await moduleItems(
      catalog: catalog,
      events: events,
      module: _ref,
    );
    expect(module.map((i) => i.cardId), contains('fresh'));
    final gate = await gateItems(
      catalog: catalog,
      events: events,
      subject: 'car',
      cards: const ['fresh'],
      now: _t0.add(const Duration(minutes: 2)),
    );
    expect(gate.map((i) => i.cardId), ['fresh']);
  });

  test('offline: a failed pull still builds the list', () async {
    await events.pull();
    db.offline = true;
    final items = await moduleItems(
      catalog: catalog,
      events: events,
      module: _ref,
    );
    expect(items.map((i) => i.cardId), ['a', 'b', 'c']);
  });
}
