import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/history/history.dart';
import 'package:tutor/model/session_index.dart';
import 'package:tutor/sync/json_tree.dart';

import '../model/samples.dart';
import '../support/fake_rtdb.dart';

const _a = '20261010-100000-aaaa';
const _b = '20261011-100000-bbbb';
const _c = '20261012-100000-cccc';

void main() {
  test('load: rows with archived flags; malformed rows skipped', () async {
    var root = setAt(null, 'tutor/v1/session_index', {
      _a: indexRow,
      _b: {...indexRow, 'auto_archived': true},
      _c: indexRow,
      'junk': indexRow,
      '20261013-100000-dddd': {'rev': 'x'},
    });
    root = setAt(root, 'tutor/v1/sessions/$_c/user', {'archived': true});
    final repo = HistoryRepo((FakeRtdb()..root = root).client());
    final rows = await repo.load();
    expect(rows.map((r) => r.sid), [_a, _b, _c]);
    final lists = splitHistory(rows);
    expect(lists.shown.map((e) => e.sid), [_a]);
    expect(lists.hidden.map((e) => e.sid), [_c, _b]);
    expect(await HistoryRepo(FakeRtdb().client()).load(), isEmpty);
  });

  test('transcript and archiving', () async {
    final db = FakeRtdb()
      ..root = setAt(null, 'tutor/v1/sessions/$_a', {
        'meta': sessionMeta,
        'msgs': {'m0001': tutorMessage},
        'user': {'archived': true},
      });
    final repo = HistoryRepo(db.client());
    final t = await repo.transcript(_a);
    expect(t.archived, isTrue);
    expect(t.view.meta!.rev, 31);
    expect(t.view.messages.single.key, 'm0001');
    await repo.setArchived(_a, archived: false);
    expect((await repo.transcript(_a)).archived, isFalse);
    final empty = await repo.transcript(_b);
    expect(empty.view.meta, isNull);
    expect(empty.archived, isFalse);
    expect(
      const HistoryEntry(
        sid: _a,
        row: SessionIndexRow(started: '', subject: '', rev: 1),
      ).hidden,
      isFalse,
    );
  });
}
