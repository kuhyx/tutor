import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:idb_shim/idb_client_memory.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/storage/device_id.dart';
import 'package:tutor/storage/kv_open.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/util/ulid.dart';

Future<void> _exercise(KvStore kv) async {
  expect(await kv.get('a'), isNull);
  await kv.set('a', 'x');
  expect(await kv.get('a'), 'x');
  await kv.remove('a');
  expect(await kv.get('a'), isNull);
}

void main() {
  test('memory, prefs and IndexedDB stores behave alike', () async {
    await _exercise(MemoryKv());
    SharedPreferences.setMockInitialValues({});
    await _exercise(await openKv());
    await _exercise(await IdbKv.open(newIdbFactoryMemory()));
  });

  test(
    'device id is minted once, persisted, corrupt values replaced',
    () async {
      final kv = MemoryKv();
      final id = await loadDeviceId(kv);
      expect(isDeviceId(id), isTrue);
      expect(await loadDeviceId(kv, mint: () => 'never'), id);
      kv.data['device_id'] = 'pc';
      const fresh = '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10';
      expect(await loadDeviceId(kv, mint: () => fresh), fresh);
    },
  );

  group('ULID', () {
    test('shape, time prefix, monotonic within a millisecond', () {
      var now = 1791731346000;
      final gen = UlidGenerator(now: () => now, random: Random(1));
      final a = gen.next();
      final b = gen.next();
      now -= 5; // the wall clock steps back
      final c = gen.next();
      now += 100;
      final d = gen.next();
      for (final id in [a, b, c, d]) {
        expect(isUlid(id), isTrue, reason: id);
      }
      expect([a, b, c, d], orderedEquals([a, b, c, d]..sort()));
      expect({a, b, c, d}, hasLength(4));
      expect(decodeTime(a), 1791731346000);
      expect(decodeTime(d), 1791731346095);
      expect(a.substring(0, 10), encodeTime(1791731346000));
      expect(isUlid(UlidGenerator().next()), isTrue);
    });

    test('increment carries and overflow is loud', () {
      final gen = UlidGenerator(now: () => 0, random: _MaxRandom());
      final first = gen.next();
      expect(first.substring(10), 'Z' * 16);
      expect(gen.next, throwsStateError);
      final carry = UlidGenerator(now: () => 0, random: _LastMaxRandom());
      final x = carry.next();
      final y = carry.next();
      expect(x.substring(24), '0Z');
      expect(y.substring(24), '10');
    });

    test('range and bad input', () {
      expect(() => encodeTime(-1), throwsArgumentError);
      expect(
        () => decodeTime('UUUUUUUUUU0000000000000000'),
        throwsFormatException,
      );
    });
  });
}

class _MaxRandom implements Random {
  @override
  int nextInt(int max) => max - 1;
  @override
  bool nextBool() => true;
  @override
  double nextDouble() => 0;
}

class _LastMaxRandom implements Random {
  int _n = 0;
  @override
  int nextInt(int max) => _n++ == 15 ? max - 1 : 0;
  @override
  bool nextBool() => true;
  @override
  double nextDouble() => 0;
}
