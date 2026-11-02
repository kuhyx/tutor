import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/coach/coach_models.dart';

import 'coach_fixtures.dart';

void main() {
  group('slugFromInput', () {
    test('takes a slug, a URL, a URL with a tail', () {
      expect(slugFromInput(' Two-Sum '), 'two-sum');
      expect(
        slugFromInput('https://leetcode.com/problems/two-sum/description/'),
        'two-sum',
      );
      expect(
        slugFromInput('leetcode.com/problems/lru-cache?envType=x'),
        'lru-cache',
      );
      expect(slugFromInput('https://leetcode.cn/problems/a1/'), 'a1');
    });

    test('refuses anything else', () {
      expect(slugFromInput(''), isNull);
      expect(slugFromInput('two sum'), isNull);
      expect(slugFromInput('https://example.com/problems/x'), isNull);
      expect(slugFromInput('https://leetcode.com/contest/x'), isNull);
      expect(slugFromInput('https://leetcode.com/problems/'), isNull);
    });
  });

  test('a list parses; missing parts are empty', () {
    final l = parseCoachList(listData);
    expect(l.lcId, 'a1b2c3d4e5f6');
    expect(l.due.single.slug, 'two-sum');
    expect(l.due.single.note, '+3 d');
    expect(l.recent.first.title, 'Reformat Department Table');
    expect(l.recent.last.title, 'lru-cache');
    expect(l.recent.last.difficulty, '');
    final none = parseCoachList(const {});
    expect(none.lcId, isNull);
    expect(none.due, isEmpty);
    expect(none.recent, isEmpty);
  });

  test('an index-keyed map is read as a list', () {
    final l = parseCoachList(const {
      'recent': {
        '1': {'slug': 'b'},
        '0': {'slug': 'a'},
      },
    });
    expect([for (final r in l.recent) r.slug], ['a', 'b']);
    expect(
      () => parseCoachList(const {
        'recent': {'x': 1},
      }),
      throwsFormatException,
    );
    expect(() => parseCoachList(const {'recent': 3}), throwsFormatException);
  });

  test('a start turn carries problem, starter code and progress', () {
    final t = parseCoachTurn(startData);
    expect(t.lcId, '0123456789ab');
    expect(t.problem!.slug, 'two-sum');
    expect(t.problem!.statementMd, contains('target'));
    expect(t.problem!.starter['python3'], startsWith('class'));
    expect((t.step, t.rung, t.turn, t.budget), (1, 'H0', 1, 16));
    expect(t.replyMd, startsWith('Restate'));
    expect(
      (t.ended, t.retest, t.banner, t.pin, t.thread),
      (false, false, null, null, null),
    );
  });

  test('a later turn has no problem; a reply pins its last block', () {
    final t = parseCoachTurn(turnData);
    expect(t.problem, isNull);
    expect(t.pin!.md, '```python\nseen = {}\n```');
    expect(t.thread, isNull);
  });

  test('a server pin wins over the reply, a table pin parses', () {
    final t = parseCoachTurn({
      ...turnData,
      'pin': {
        'table': {
          'name': 'Department',
          'columns': ['id'],
          'rows': [
            [1],
          ],
        },
      },
    });
    expect(t.pin!.table!.name, 'Department');
    expect(t.pin!.table!.rows, [
      ['1'],
    ]);
    final md = parseCoachTurn({
      ...turnData,
      'pin': {'md': 'x = 1'},
    });
    expect(md.pin!.md, 'x = 1');
    expect(
      () => parseCoachTurn({...turnData, 'pin': 'str'}),
      throwsFormatException,
    );
  });

  test('banner, retest, ended and a stored thread parse', () {
    final t = parseCoachTurn({
      'lc_id': 'x',
      'retest': true,
      'banner': 'Do NOT submit',
      'ended': true,
      'thread': [
        {'mine': true, 'md': 'hi'},
        {
          'mine': false,
          'grid': {
            'columns': ['a'],
            'rows': [
              [1],
            ],
          },
        },
      ],
    });
    expect((t.retest, t.banner, t.ended), (true, 'Do NOT submit', true));
    expect(t.thread!.first.mine, isTrue);
    expect(t.thread!.last.grid!.columns, ['a']);
    expect(
      () => parseCoachTurn(const {
        'lc_id': 'x',
        'thread': [1],
      }),
      throwsFormatException,
    );
  });

  group('extractPin', () {
    test('last fenced block or pipe table, else null', () {
      expect(extractPin('plain prose?'), isNull);
      expect(
        extractPin('a\n```sql\nSELECT 1\n```\nb'),
        '```sql\nSELECT 1\n```',
      );
      const table = '| a | b |\n| - | - |\n| 1 | 2 |';
      expect(extractPin('look:\n\n$table\n\nwhy?'), table);
      expect(
        extractPin('```x\n1\n```\n\n$table\n\n```y\n2\n```'),
        '```y\n2\n```',
      );
    });
  });

  test('a run report: examples, errors, SQL tables', () {
    final r = parseRunReport(runData);
    expect(r.error, isNull);
    expect(r.examples.map((e) => e.ok), [true, false, false]);
    expect(r.examples[1].got, '[1,2]');
    expect(r.examples[1].expected, '[0,2]');
    expect(r.examples[2].error, 'TypeError');
    final s = parseRunReport(sqlRunData).examples.single;
    expect(s.gotTable!.rows[1], ['2', 'NULL']);
    expect(s.expectedTable!.rows[1], ['2', '5']);
    expect(parseRunReport(const {'error': 'timeout'}).error, 'timeout');
    expect(
      () => parseRunReport(const {
        'examples': [3],
      }),
      throwsFormatException,
    );
  });

  test('a post-mortem parses its cards and proposals', () {
    final t = parseCoachTurn(postmortemData);
    final p = t.postmortem!;
    expect(p.summaryMd, contains('step'));
    expect(p.cards.single.back, 'hash map');
    expect(p.proposals.map((e) => e.name), [
      'conditional aggregation',
      'quoting',
    ]);
    expect(p.proposals.first.aliases, ['sum case']);
    expect(p.proposals.last.aliases, isEmpty);
    expect(p.proposals.last.properties, ['text value vs identifier']);
    expect(parseCoachTurn(const {'lc_id': 'x'}).postmortem, isNull);
  });
}
