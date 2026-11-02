/// Contract-shaped fixtures (handoff 20261102-sql-practice-contract.md);
/// when DOCS-contract-sql.md differs, fix them here.
library;

const Map<String, Object?> listData = {
  'topics': ['basics', 'joins-null'],
  'drills': [
    {
      'id': 'basics-1',
      'title': 'Count rows',
      'topic': 'basics',
      'kind': 'write',
      'source': 'builtin',
    },
    {
      'id': 'basics-2',
      'title': 'Predict NULL',
      'topic': 'basics',
      'kind': 'predict',
      'source': 'builtin',
    },
    {
      'id': 'gen-9',
      'title': 'Left join gaps',
      'topic': 'joins-null',
      'kind': 'write',
      'source': 'generated',
    },
  ],
};

const Map<String, Object?> _writeMeta = {
  'id': 'basics-1',
  'title': 'Count rows',
  'topic': 'basics',
  'kind': 'write',
  'source': 'builtin',
};

const Map<String, Object?> writeDrillData = {
  'meta': _writeMeta,
  'task_md': 'Count the **employees**.\n\n```sql\nSELECT 1;\n```',
  'schema_sql': 'CREATE TABLE emp (id INT, name TEXT);',
  'tables': {
    'emp': {
      'columns': ['id', 'name'],
      'rows': [
        [1, 'Ann'],
        [2, null],
      ],
    },
  },
  'expected_preview': [
    ['2'],
  ],
};

const Map<String, Object?> predictDrillData = {
  'meta': {
    'id': 'basics-2',
    'title': 'Predict NULL',
    'topic': 'basics',
    'kind': 'predict',
    'source': 'builtin',
  },
  'task_md': 'What does it print?',
  'tables': {
    'emp': {
      'columns': ['id'],
      'rows': [
        [1],
      ],
    },
  },
  'query': 'SELECT 1',
};

const Map<String, Object?> runBadData = {
  'ok': true,
  'columns': ['n'],
  'rows': [
    [3],
    [null],
  ],
  'expected_rows': [
    [2],
  ],
  'match': false,
  'cell_diff': [
    [0, 0, '2', '3'],
  ],
  'extra': [
    ['NULL'],
  ],
};

const Map<String, Object?> runGoodData = {
  'ok': true,
  'columns': ['n'],
  'rows': [
    ['2'],
  ],
  'expected_rows': [
    ['2'],
  ],
  'match': true,
};

const Map<String, Object?> lessonTurnData = {
  'lesson_id': 'a1b2c3d4e5f6',
  'topic': 'basics',
  'turn': 3,
  'progress': {
    'concept': 'NULL comparisons',
    'index': 0,
    'total': 2,
    'phase': 'teach',
    'checks_left': 0,
  },
  'question_md':
      'Which names does this return, and why?\n\n'
      '```sql\nSELECT name FROM customers WHERE age <> 2;\n```',
  'tables': {
    'customers': {
      'columns': ['id', 'name', 'age'],
      'rows': [
        [1, 'Ann', 2],
        [2, 'Bob', null],
      ],
    },
  },
  'feedback_md': 'Not quite.',
  'summary_md': '| a | b |\n|---|---|\n| UNKNOWN | no row |',
  'result': {
    'columns': ['name'],
    'rows': [
      ['Ann'],
    ],
  },
};
