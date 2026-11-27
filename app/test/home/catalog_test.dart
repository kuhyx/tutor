import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/home/remote_bits.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/json_tree.dart';

import '../model/samples.dart';
import '../support/fake_rtdb.dart';

void main() {
  test('parseSubject: meta, plan, cards (bad ones skipped), concepts', () {
    final s = parseSubject('car', {
      'meta': subjectMeta,
      'plan': plan,
      'cards': {
        'b': {...card, 'order': 1},
        'a': card,
        'bad': {'front': 1},
      },
      'concepts': [
        {'name': 'n', 'at': 1},
      ],
    })!;
    expect(s.plan!.rev, 2);
    expect(s.cards.keys, unorderedEquals(['a', 'b']));
    expect(s.cardsOf('engine-basics').map((e) => e.key), ['b', 'a']);
    expect(s.concepts.single.name, 'n');
    expect(parseSubject('x', null), isNull);
    expect(parseSubject('x', {'plan': plan}), isNull);
    expect(
      parseSubject('x', {
        'meta': {'title': 1},
      }),
      isNull,
    );
    expect(parseSubject('x', {'meta': subjectMeta})!.plan, isNull);
  });

  test('cached and fetch', () async {
    final db = FakeRtdb()
      ..root = setAt(null, 'tutor/v1-e2e/subjects/car', {'meta': subjectMeta});
    final kv = MemoryKv();
    final catalog = Catalog(client: db.client(), kv: kv);
    expect(await catalog.cached(), isEmpty);
    expect(await catalog.fetch('Bad Id'), isNull);
    final car = await catalog.fetch('car');
    expect(car!.meta.title, 'How a car works');
    expect((await catalog.cached()).keys, ['car']);
  });

  test('prefs and stats', () async {
    final db = FakeRtdb();
    final client = db.client();
    final kv = MemoryKv();
    expect(await fetchStats(client, kv), isNull);
    db.root = setAt(db.root, 'tutor/v1-e2e/stats', stats);
    expect((await fetchStats(client, kv))!.today.target, 60);
  });

  test('stats are kept and read back offline', () async {
    final db = FakeRtdb()..root = setAt(null, 'tutor/v1-e2e/stats', stats);
    final kv = MemoryKv();
    await fetchStats(db.client(), kv);
    db.offline = true;
    expect((await fetchStats(db.client(), kv))!.today.target, 60);
    db
      ..offline = false
      ..root = setAt(db.root, 'tutor/v1-e2e/stats', null);
    expect(await fetchStats(db.client(), kv), isNull);
    db.offline = true;
    expect(await fetchStats(db.client(), kv), isNull);
    kv.data[kStatsCacheKey] = '{not json';
    expect(await fetchStats(db.client(), kv), isNull);
  });
}
