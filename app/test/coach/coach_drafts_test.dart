import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/coach/coach_drafts.dart';
import 'package:tutor/sql/lesson_models.dart';
import 'package:tutor/storage/kv_store.dart';

void main() {
  late MemoryKv kv;
  late CoachDrafts d;
  setUp(() {
    kv = MemoryKv();
    d = CoachDrafts(kv);
  });

  test('code is kept per problem and language', () async {
    expect(await d.code('a', 'python3'), isNull);
    await d.saveCode('a', 'python3', 'x = 1');
    await d.saveCode('a', 'mysql', 'SELECT 1');
    expect(await d.code('a', 'python3'), 'x = 1');
    expect(await d.code('a', 'mysql'), 'SELECT 1');
    expect(await d.code('b', 'python3'), isNull);
  });

  test('the chosen language defaults to python3', () async {
    expect(await d.lang('a'), 'python3');
    await d.saveLang('a', 'mysql');
    expect(await d.lang('a'), 'mysql');
    await kv.set('coach.lang.a', 'cobol');
    expect(await d.lang('a'), 'python3');
  });

  test('a thread round-trips, grids too; damage reads as empty', () async {
    final thread = <Bubble>[
      (mine: true, md: 'hi', grid: null),
      (
        mine: false,
        md: null,
        grid: (
          name: '',
          columns: ['a'],
          rows: [
            ['1'],
          ],
        ),
      ),
    ];
    await d.saveThread('s-1', thread);
    final back = await d.thread('s-1');
    expect(back.first.md, 'hi');
    expect(back.last.grid!.rows, [
      ['1'],
    ]);
    expect(await d.thread('none'), isEmpty);
    await kv.set('coach.thread.s-1', '{oops');
    expect(await d.thread('s-1'), isEmpty);
    await kv.set('coach.thread.s-1', '{"a":1}');
    expect(await d.thread('s-1'), isEmpty);
    await kv.set('coach.thread.s-1', '[1,{"mine":true,"md":"ok"}]');
    expect((await d.thread('s-1')).single.md, 'ok');
  });
}
