import 'package:tutor/sync/json_tree.dart';

import '../support/fake_rtdb.dart';

const Map<String, Object?> paperData = {
  'mock_id': 'm1',
  'started_ms': 1000000,
  'deadline_ms': 1000000 + 3600000,
  'minutes': 60,
  'notes': ['model was down; 2 questions are from the seed bank'],
  'tasks': [
    {
      'id': 'q1',
      'section': 'py_mcq',
      'title': 'Q1',
      'topic': 'lists',
      'prompt_md': 'What does this print?',
      'code': 'print([1, 2][::-1])',
      'options': ['[2, 1]', '[1, 2]', 'None', 'Error'],
    },
    {
      'id': 'q2',
      'section': 'py_mcq',
      'title': 'Q2',
      'topic': 'dicts',
      'prompt_md': 'Pick the output.',
      'code': 'print(len({}))',
      'options': ['0', '1', 'None', 'Error'],
    },
    {
      'id': 'p1',
      'section': 'py_code',
      'title': 'Palindrome',
      'topic': 'palindrome',
      'prompt_md': 'Longest palindromic substring.',
      'starter': 'def f(s):\n    pass\n',
    },
    {
      'id': 's1',
      'section': 'sql',
      'title': 'Join',
      'topic': 'joins-null',
      'prompt_md': 'List names.',
      'tables': {
        'c': {
          'columns': ['id', 'name'],
          'rows': [
            ['1', 'Ann'],
          ],
        },
      },
      'sample': [
        ['Ann'],
      ],
    },
  ],
};

const Map<String, Object?> resultData = {
  'score': 1,
  'total': 4,
  'percent': 25,
  'tasks': [
    {
      'id': 'q1',
      'section': 'py_mcq',
      'title': 'Q1',
      'topic': 'lists',
      'correct': true,
      'detail': {
        'options': ['[2, 1]', '[1, 2]', 'None', 'Error'],
        'correct_option': 0,
        'chosen': 0,
        'output': '[2, 1]',
      },
    },
    {
      'id': 'q2',
      'section': 'py_mcq',
      'title': 'Q2',
      'topic': 'dicts',
      'correct': false,
      'detail': {
        'options': ['0', '1', 'None', 'Error'],
        'correct_option': 0,
        'chosen': 1,
        'output': '0',
      },
    },
    {
      'id': 'p1',
      'section': 'py_code',
      'title': 'Palindrome',
      'topic': 'palindrome',
      'correct': false,
      'detail': {
        'passed': 1,
        'total': 3,
        'failed': [
          {'n': 2, 'input': 'cbbd', 'expected': 'bb', 'actual': 'c'},
        ],
      },
      'link': {'kind': 'coach', 'slug': 'longest-palindromic-substring'},
    },
    {
      'id': 's1',
      'section': 'sql',
      'title': 'Join',
      'topic': 'joins-null',
      'correct': false,
      'answer': 'select 1',
      'detail': {
        'columns': ['name'],
        'rows': [
          ['Bob'],
        ],
        'expected_rows': [
          ['Ann'],
        ],
        'cell_diff': [
          [0, 0, 'Ann', 'Bob'],
        ],
      },
      'link': {'kind': 'lesson', 'topic': 'joins-null'},
    },
  ],
};

/// The `mock` request bodies written so far, oldest first.
List<Map<String, dynamic>> mockBodies(FakeRtdb db) {
  final reqs = getAt(db.root, 'tutor/v1-e2e/requests') as Map<String, dynamic>?;
  if (reqs == null) return const [];
  return [
    for (final k in reqs.keys.toList()..sort())
      ((reqs[k] as Map<String, dynamic>)['req'] as Map<String, dynamic>)['body']
          as Map<String, dynamic>,
  ];
}
