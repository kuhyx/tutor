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
    expect(l.recent.first.lcId, lcId);
    expect(l.recent.first.title, 'Two Sum');
    expect(l.recent.first.updatedMs, 5);
    expect(l.recent.last.title, 'lru-cache');
    expect(l.recent.last.phase, 'work');
    expect(l.clusters.single.problems, ['two-sum', 'valid-anagram']);
    expect(l.due.single.title, 'Group Anagrams');
    expect(l.due.single.dueMs, 9);
    final none = parseCoachList(const {});
    expect(none.recent, isEmpty);
    expect(none.clusters, isEmpty);
    expect(none.due, isEmpty);
    expect(
      parseCoachList(const {
        'due': [
          {'slug': 'x'},
        ],
      }).due.single.title,
      'x',
    );
  });

  test('an index-keyed map is read as a list', () {
    final l = parseCoachList(const {
      'recent': {
        '1': {'lc_id': 'b', 'slug': 'b'},
        '0': {'lc_id': 'a', 'slug': 'a'},
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

  test('an opened algorithm problem', () {
    final o = parseOpened(openData);
    expect(o.lcId, lcId);
    expect(
      (o.slug, o.title, o.difficulty, o.kind),
      ('two-sum', 'Two Sum', 'easy', 'algo'),
    );
    expect(o.langs, ['python3', 'javascript', 'typescript']);
    expect(o.starter['python3'], startsWith('class'));
    expect(o.statementMd, contains('target'));
    expect(o.replyMd, startsWith('Restate'));
    expect(o.retest, isFalse);
    expect(o.thread, isNull);
    expect(o.state!.gate.open, isFalse);
    expect(o.state!.budget, 16);
  });

  test('an opened SQL problem defaults to mysql; resume has a thread', () {
    final o = parseOpened(sqlOpenData);
    expect(o.lang, 'mysql');
    expect(o.langs, ['mysql', 'postgresql']);
    expect(o.state, isNull);
    final min = parseOpened(const {'lc_id': 'x', 'slug': 's'});
    expect(min.langs, ['python3']);
    expect((min.lang, min.kind, min.title), ('python3', 'algo', 's'));
    final r = parseOpened({
      ...openData,
      'reply_md': null,
      'retest': true,
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
    expect((r.replyMd, r.retest), (null, true));
    expect(r.thread!.first.mine, isTrue);
    expect(r.thread!.last.grid!.columns, ['a']);
    expect(
      () => parseOpened({
        ...openData,
        'thread': [1],
      }),
      throwsFormatException,
    );
    expect(
      () => parseOpened({
        ...openData,
        'starter': {'x': 1},
      }),
      throwsFormatException,
    );
  });

  test('state parses with defaults', () {
    final s = parseState(stateWork)!;
    expect((s.phase, s.rung, s.used, s.budget), ('work', 'H1', 3, 16));
    expect(
      (s.gate.kind, s.gate.tries, s.gate.open, s.ranOk),
      ('req', 1, true, false),
    );
    final d = parseState(const <String, Object?>{})!;
    expect(
      (d.phase, d.gate.open, d.over, d.revealed, d.rung),
      ('work', true, false, false, null),
    );
    expect(parseState(null), isNull);
    expect(
      parseState(const {
        'gate': {'forced': true},
      })!.gate.open,
      isFalse,
    );
  });

  test('a turn', () {
    final t = parseCoachTurn(turnData);
    expect(t.replyMd, contains('seen[3]'));
    expect((t.held, t.note, t.banner, t.exit), (false, null, null, null));
    expect(t.choices, isEmpty);
    final h = parseCoachTurn(const {
      'held': true,
      'note': 'Not yet',
      'banner': 'budget',
      'choices': ['write it', 'hint!', 'reveal'],
      'exit': {'ok': false, 'missing': 'the ELSE'},
    });
    expect((h.held, h.note, h.banner), (true, 'Not yet', 'budget'));
    expect(h.choices, ['write it', 'hint!', 'reveal']);
    expect(
      (h.exit!.ok, h.exit!.missing, h.exit!.summaryMd),
      (false, 'the ELSE', null),
    );
    expect(h.state, isNull);
    expect(
      parseCoachTurn(const {
        'exit': {'ok': true, 'summary_md': '| a |'},
      }).exit!.summaryMd,
      '| a |',
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
      expect(extractPin('```x\n1\n```\n\n$table'), table);
    });
  });
}
