import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sql/sql_drafts.dart';
import 'package:tutor/storage/kv_store.dart';

void main() {
  test('sql and grid round trip per drill; nothing saved = empty', () async {
    final kv = MemoryKv();
    final d = SqlDrafts(kv);
    expect(await d.sql('a'), '');
    expect(await d.grid('a'), isEmpty);
    await d.saveSql('a', 'select 1');
    await d.saveGrid('a', const [
      ['1', ''],
    ]);
    expect(await d.sql('a'), 'select 1');
    expect(await d.sql('b'), '');
    expect(await d.grid('a'), [
      ['1', ''],
    ]);
  });

  test('a damaged grid reads as empty', () async {
    final kv = MemoryKv();
    final d = SqlDrafts(kv);
    await kv.set('sql.grid.a', '{oops');
    expect(await d.grid('a'), isEmpty);
    await kv.set('sql.grid.a', '{"a":1}');
    expect(await d.grid('a'), isEmpty);
    await kv.set('sql.grid.a', '[[1,null],"x"]');
    expect(await d.grid('a'), [
      ['1', 'null'],
    ]);
  });
}
