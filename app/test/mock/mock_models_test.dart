import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/mock/mock_models.dart';
import 'package:tutor/mock/mock_requests.dart';

import 'mock_fixtures.dart';

void main() {
  test('a paper keeps its tasks in order with their parts', () {
    final p = parsePaper(paperData);
    expect(p.mockId, 'm1');
    expect(p.minutes, 60);
    expect(p.deadlineMs - p.startedMs, 3600000);
    expect(p.notes, hasLength(1));
    expect(p.tasks.map((t) => t.section), [
      MockSection.pyMcq,
      MockSection.pyMcq,
      MockSection.pyCode,
      MockSection.sql,
    ]);
    expect(p.tasks.first.options, hasLength(4));
    expect(p.tasks[2].starter, contains('def f'));
    expect(p.tasks[3].tables.single.name, 'c');
    expect(p.tasks[3].sample, [
      ['Ann'],
    ]);
  });

  test('a missing deadline is start plus minutes', () {
    final p = parsePaper({'mock_id': 'm', 'started_ms': 5, 'minutes': 2});
    expect(p.deadlineMs, 5 + 120000);
    expect(p.tasks, isEmpty);
  });

  test('an unknown section is a format error', () {
    expect(
      () => parsePaper({
        'mock_id': 'm',
        'started_ms': 1,
        'tasks': [
          {'id': 'x', 'section': 'essay'},
        ],
      }),
      throwsFormatException,
    );
  });

  test('a result lists items, links and details', () {
    final r = parseResult(resultData);
    expect((r.score, r.total, r.percent), (1, 4, 25));
    expect(r.items[0].link, isNull);
    expect(r.items[2].link, (
      kind: 'coach',
      target: 'longest-palindromic-substring',
    ));
    expect(r.items[3].link, (kind: 'lesson', target: 'joins-null'));
    expect(r.items[3].answer, 'select 1');
  });

  test('a bare result derives score and percent', () {
    final r = parseResult({
      'tasks': [
        {'id': 'a', 'section': 'sql', 'correct': true},
        {'id': 'b', 'section': 'sql'},
      ],
    });
    expect((r.score, r.total, r.percent), (1, 2, 50));
    expect(parseResult(const {}).percent, 0);
  });

  test('a run is a grid, an error or example verdicts', () {
    final grid = parseRun({
      'columns': ['a'],
      'rows': [
        [1, null],
      ],
    });
    expect(grid.rows, [
      ['1', 'NULL'],
    ]);
    expect(grid.ok, isTrue);
    final bad = parseRun({'ok': false, 'error': 'syntax'});
    expect((bad.ok, bad.error), (false, 'syntax'));
    final py = parseRun({
      'examples': [
        {'n': 1, 'ok': true, 'input': 'ab', 'expected': 1, 'actual': 1},
        {'n': 2, 'input': 'x', 'expected': 'y', 'actual': null, 'error': 'E'},
      ],
    });
    expect(py.examples.map((e) => e.ok), [true, false]);
    expect(py.examples[0].input, '"ab"');
    expect(py.examples[1].error, 'E');
  });

  test('request bodies name their op', () {
    expect(mockStart(45).body, {'op': 'start', 'minutes': 45});
    expect(mockAnswer('m', 't', 'a', 9).body, {
      'op': 'answer',
      'mock_id': 'm',
      'task': 't',
      'answer': 'a',
      'ts': 9,
    });
    expect(mockRun('m', 't', 'a').body['op'], 'run');
    expect(mockFinish('m').body, {'op': 'finish', 'mock_id': 'm'});
  });
}
