import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/focus/focus_send.dart';
import 'package:tutor/storage/kv_store.dart';

void main() {
  test('cachedStatus: nothing, corrupt, then a stored result', () async {
    final kv = MemoryKv();
    expect(await cachedStatus(kv), isNull);
    await kv.set('focus.status', '[1]');
    expect(await cachedStatus(kv), isNull);
    await cacheStatus(kv, {
      'day': '2026-11-02',
      'active': null,
      'projects': <Object?>[],
      'gates': <Object?>[],
      'subjects': <Object?>[],
    });
    expect((await cachedStatus(kv))!.day, '2026-11-02');
  });
}
