/// Result shapes of DOCS-contract-coach.md.
library;

const lcId = '0123456789ab';

const Map<String, Object?> listData = {
  'recent': [
    {
      'lc_id': lcId,
      'slug': 'two-sum',
      'title': 'Two Sum',
      'phase': 'work',
      'updated_ms': 5,
    },
    {'lc_id': 'ffffffffffff', 'slug': 'lru-cache'},
  ],
  'clusters': [
    {
      'name': 'hashing',
      'problems': ['two-sum', 'valid-anagram'],
    },
  ],
  'due': [
    {'slug': 'group-anagrams', 'title': 'Group Anagrams', 'due_ms': 9},
  ],
};

const Map<String, Object?> stateWork = {
  'phase': 'work',
  'gate': {'kind': 'req', 'tries': 1, 'max': 3, 'open': true},
  'turns': {'used': 3, 'budget': 16, 'over': false},
  'rung': 'H1',
  'ran_ok': false,
};

const Map<String, Object?> openData = {
  'lc_id': lcId,
  'slug': 'two-sum',
  'title': 'Two Sum',
  'difficulty': 'easy',
  'kind': 'algo',
  'lang': 'python3',
  'langs': ['python3', 'javascript', 'typescript'],
  'statement_md': 'Find two numbers that add up to `target`.',
  'starter': {
    'python3': 'class Solution:\n    pass\n',
    'javascript': 'var twoSum = function() {};\n',
  },
  'retest': false,
  'state': {
    'phase': 'gate',
    'gate': {'kind': 'req', 'tries': 0, 'max': 3, 'open': false},
    'turns': {'used': 0, 'budget': 16},
  },
  'reply_md': 'Restate it. What breaks if the array has duplicates?',
};

const Map<String, Object?> sqlOpenData = {
  'lc_id': lcId,
  'slug': 'reformat-department-table',
  'title': 'Reformat Department Table',
  'kind': 'sql',
  'langs': ['mysql', 'postgresql'],
  'statement_md': 'Pivot the table.',
  'starter': {'mysql': '# Write your MySQL query statement below\n'},
  'reply_md': 'What columns will the output have?',
};

const Map<String, Object?> turnData = {
  'state': stateWork,
  'reply_md':
      'Consider this:\n\n```python\nseen = {}\n```\n\nWhat is `seen[3]`?',
};

const Map<String, Object?> runData = {
  'state': stateWork,
  'ok': false,
  'passed': 1,
  'total': 3,
  'examples': [
    {'n': 1, 'ok': true, 'got': '[0,1]', 'expected': '[0,1]'},
    {'n': 2, 'ok': false, 'got': '[1,2]', 'expected': '[0,2]'},
    {'n': 3, 'ok': false, 'error': 'TypeError'},
  ],
};

const Map<String, Object?> sqlRunData = {
  'ok': false,
  'examples': [
    {
      'n': 1,
      'ok': false,
      'columns': ['id', 'Jan'],
      'rows': [
        [1, 100],
        [2, null],
      ],
      'expected_rows': [
        [1, 100],
        [2, 5],
      ],
      'cell_diff': [
        [1, 1, '5', 'NULL'],
      ],
    },
  ],
};

const Map<String, Object?> cardsData = {
  'cards': [
    {
      'id': 'hash-lookup',
      'front': 'Toolbox: one pass, O(1) lookup?',
      'back': 'hash map',
      'new': true,
    },
  ],
  'proposals': [
    {
      'name': 'conditional aggregation',
      'aliases': ['sum case'],
      'properties': ['per-row branch', 'collapse rows'],
    },
    {
      'name': 'quoting',
      'properties': ['text value vs identifier'],
    },
  ],
  'refused': [
    {'name': 'nest', 'reason': 'nests with hash map'},
  ],
  'anki': {'delivered': false, 'line': 'Anki is closed'},
};
