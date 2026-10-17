/// Contract-shaped sample records, copied from the DOCS-contract examples.
library;

const Map<String, Object> sessionMeta = {
  'subject': 'automation',
  'card': {'id': 'ld-x', 'front': 'What is a rung?'},
  'started': 1000,
  'stopped': false,
  'card_done': false,
  'check_open': true,
  'n': 14,
  'rev': 31,
  'clock': {
    'active_seconds': 412.5,
    'paused_reason': 'idle',
    'awaiting_since': 2000,
    'reply_timeout_s': 600,
  },
  'credited_minutes': 6,
  'busy': {
    'rid': '01JABCDEFGHJKMNPQRSTVWXYZ0',
    'phase': 'checking_images',
    'since': 3000,
    'text': 'pending learner text',
  },
};

const Map<String, Object> tutorMessage = {
  'role': 'tutor',
  'text': 'markdown',
  'questions': ['q1', 'q2'],
  'low_effort': true,
  'check': {'question': 'q', 'concept': 'c'},
  'check_result': {'passed': true, 'feedback': 'f'},
  'images': [
    {
      'url': 'https://upload.wikimedia.org/a/800px-b.jpg',
      'title': 't',
      'author': 'a',
      'licence': 'CC BY-SA 4.0',
      'licence_url': 'https://creativecommons.org/x',
      'page_url': 'https://commons.wikimedia.org/wiki/File:b.jpg',
      'term': 'relay',
    },
  ],
  'diagrams': [
    {'title': 'd', 'svg': '<svg/>'},
  ],
  'mastered_new': ['normally closed contact'],
  'notices': ['Card removed: What is a coil?'],
  'card_done': true,
  'at': 5000,
};

const Map<String, Object> learnerMessage = {
  'role': 'learner',
  'text': 'answer',
  'at': 6000,
  'rid': '01JABCDEFGHJKMNPQRSTVWXYZ0',
  'dev': '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10',
};

const Map<String, Object> receipt = {
  'entry_id': '20261012-170448-5b71-m6',
  'recorded': true,
  'minutes': 1,
  'minutes_today': 23,
  'error': 'cap',
  'at': 7000,
};

const Map<String, Object> indexRow = {
  'started': '2026-10-12 17:04',
  'subject': 'automation',
  'cards': [
    {'id': 'ld-x', 'front': 'f', 'done': true, 'done_here': false},
  ],
  'active_minutes': 12,
  'credited_minutes': 12,
  'stopped': true,
  'auto_archived': false,
  'rev': 31,
};

const Map<String, Object> subjectMeta = {
  'title': 'How a car works',
  'goal': 'I want to learn how a car works',
  'status': 'review_only',
  'created': 100,
  'plan_rev': 2,
  'rev': 7,
  'origin': 'generated',
};

const Map<String, Object> plan = {
  'rev': 2,
  'status': 'draft',
  'notes': 'why this order',
  'modules': [
    {
      'id': 'engine-basics',
      'title': 'The four-stroke engine',
      'summary': 's',
      'requires': ['intro'],
      'depth': 1,
      'prefixes': ['eng'],
      'status': 'failed',
      'recall': 0.5,
      'cards': 3,
      'error': 'no sources',
    },
  ],
  'history': [
    {'rev': 1, 'comment': 'less history', 'at': 9},
  ],
};

const Map<String, Object> card = {
  'module': 'engine-basics',
  'order': 3,
  'front': 'front',
  'back': 'back',
  'source': 'https://example.org',
  'excerpt': 'six to forty words verbatim',
  'requires': ['eng-a'],
  'rev': 1,
  'origin': 'generated',
  'created': 11,
  'suspended': false,
};

const Map<String, Object> worker = {
  'host': 'pc',
  'pid': 42,
  'version': '1.0.0',
  'started': 1,
  'beat': 2,
  'lanes': {'chat': '01JABCDEFGHJKMNPQRSTVWXYZ0'},
  'skew_ms': 12,
};

const Map<String, Map<String, Object>> stats = {
  'today': {
    'day': '2026-10-12',
    'credited_minutes': 23,
    'target': 60,
    'new': 4,
    'new_cap': 10,
  },
  'days': {
    '2026-10-12': {'minutes': 23, 'taught': 4, 'reviews': 31},
  },
};
