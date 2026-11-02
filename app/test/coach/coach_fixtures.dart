/// Provisional lc_* result shapes (handoff 20261102-problem-coach-contract
/// s7). DOCS-contract-coach.md (K4) is not pushed yet: when it differs, fix
/// these and lib/coach/coach_models.dart only.
library;

const Map<String, Object?> listData = {
  'lc_id': 'a1b2c3d4e5f6',
  'due': [
    {
      'slug': 'two-sum',
      'title': 'Two Sum',
      'difficulty': 'Easy',
      'note': '+3 d',
    },
  ],
  'recent': [
    {
      'slug': 'reformat-department-table',
      'title': 'Reformat Department Table',
      'difficulty': 'Easy',
    },
    {'slug': 'lru-cache'},
  ],
};

const Map<String, Object?> startData = {
  'lc_id': '0123456789ab',
  'problem': {
    'slug': 'two-sum',
    'title': 'Two Sum',
    'difficulty': 'Easy',
    'statement_md': 'Find two numbers that add up to `target`.',
    'starter': {
      'python3': 'class Solution:\n    pass\n',
      'mysql': '# Write your MySQL query statement below\n',
    },
  },
  'step': 1,
  'rung': 'H0',
  'turn': 1,
  'budget': 16,
  'msg_md': 'Restate it. What breaks if the array has duplicates?',
};

const Map<String, Object?> turnData = {
  'lc_id': '0123456789ab',
  'step': 2,
  'turn': 2,
  'msg_md': 'Consider this:\n\n```python\nseen = {}\n```\n\nWhat is `seen[3]`?',
};

const Map<String, Object?> runData = {
  'examples': [
    {'n': 1, 'ok': true, 'got': '[0,1]', 'expected': '[0,1]'},
    {'n': 2, 'ok': false, 'got': '[1,2]', 'expected': '[0,2]'},
    {'n': 3, 'ok': false, 'error': 'TypeError'},
  ],
};

const Map<String, Object?> sqlRunData = {
  'examples': [
    {
      'n': 1,
      'ok': false,
      'got_table': {
        'columns': ['id', 'Jan'],
        'rows': [
          [1, 100],
          [2, null],
        ],
      },
      'expected_table': {
        'columns': ['id', 'Jan'],
        'rows': [
          [1, 100],
          [2, 5],
        ],
      },
    },
  ],
};

const Map<String, Object?> postmortemData = {
  'lc_id': '0123456789ab',
  'ended': true,
  'postmortem': {
    'summary_md': '| step | rung |\n| --- | --- |\n| 1 | H0 |',
    'cards': [
      {'front': 'one pass, O(1) lookup of seen values', 'back': 'hash map'},
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
  },
};
