/// Fixture sessions: the live one mid-turn, a stopped one, an
/// auto-archived one, and their history rows.
library;

/// The live session's id.
const fixtureLiveSid = '20261012-170448-5b71';
const String _sid = fixtureLiveSid;
const _old = '20261011-090000-a1b2';
const _older = '20261010-200000-c3d4';

// Joined without separators: the parts are one SVG document.
const _svg = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 80">',
  '<g stroke="#211D1B" stroke-width="2" fill="none">',
  '<line x1="10" y1="10" x2="10" y2="70"/>',
  '<line x1="210" y1="10" x2="210" y2="70"/>',
  '<line x1="10" y1="40" x2="70" y2="40"/>',
  '<line x1="70" y1="25" x2="70" y2="55"/>',
  '<line x1="90" y1="25" x2="90" y2="55"/>',
  '<line x1="90" y1="40" x2="150" y2="40"/>',
  '<circle cx="170" cy="40" r="15"/>',
  '<line x1="185" y1="40" x2="210" y2="40"/></g></svg>',
];

/// `sessions` and `session_index`, relative to [now] (ms).
Map<String, Object?> fixtureSessions(int now) => {
  'sessions': {
    _sid: {
      'meta': {
        'subject': 'car',
        'card': {'id': 'eng-strokes', 'front': 'What are the four strokes?'},
        'started': now - 20 * 60000,
        'check_open': true,
        'n': 4,
        'rev': 9,
        'clock': {
          'active_seconds': 840.0,
          'awaiting_since': now - 30000,
          'reply_timeout_s': 600,
        },
        'credited_minutes': 14,
      },
      'msgs': {
        'm0001': {'role': 'card', 'text': 'What are the four strokes?'},
        'm0002': {
          'role': 'tutor',
          'text':
              'Before I explain: what do you **already** know about '
              'how an engine turns fuel into motion?\n\n'
              '- a piston moves in a *cylinder*\n- `TDC` = top dead centre',
          'questions': ['What moves inside the cylinder?'],
          'at': now - 15 * 60000,
        },
        'm0003': {
          'role': 'learner',
          'text': 'Q1: What moves inside the cylinder?\nA: The piston.',
          'at': now - 14 * 60000,
        },
        'm0004': {
          'role': 'tutor',
          'text':
              'Right. The piston goes down and up twice per cycle: '
              '**intake, compression, power, exhaust**.',
          'images': [
            {
              'url':
                  'https://upload.wikimedia.org/wikipedia/commons/d/dc/'
                  '4StrokeEngine_Ortho_3D_Small.gif',
              'title': 'Four-stroke engine',
              'author': 'Zephyris',
              'licence': 'CC BY-SA 3.0',
              'licence_url': 'https://creativecommons.org/licenses/by-sa/3.0',
              'page_url':
                  'https://commons.wikimedia.org/wiki/'
                  'File:4StrokeEngine_Ortho_3D_Small.gif',
            },
          ],
          'diagrams': [
            {'title': 'Ignition circuit', 'svg': _svg.join()},
          ],
          'check_result': {'passed': true, 'feedback': 'Piston: correct.'},
          'questions': ['Which stroke makes the power?'],
          'check': {
            'question': 'Why does the engine need two crank turns?',
            'concept': 'four-stroke cycle',
          },
          'mastered_new': ['piston'],
          'at': now - 10 * 60000,
        },
      },
    },
    _old: {
      'user': {'archived': false},
    },
  },
  'session_index': {
    _old: {
      'started': '2026-10-11 09:00',
      'subject': 'car',
      'cards': [
        {
          'id': 'eng-crank',
          'front': 'What does the crankshaft do?',
          'done': true,
          'done_here': true,
        },
      ],
      'active_minutes': 18,
      'credited_minutes': 18,
      'stopped': true,
      'rev': 12,
    },
    _older: {
      'started': '2026-10-10 20:00',
      'subject': 'car',
      'cards': [
        {'id': 'eng-valves', 'front': 'What opens the valves?'},
      ],
      'active_minutes': 1,
      'stopped': true,
      'auto_archived': true,
      'rev': 3,
    },
  },
};
