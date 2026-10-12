/// Contract-shaped fixture data for screenshots: a drafted subject, an
/// active one with cards, a live session mid-turn, history and stats.
library;

import 'fixture_sessions.dart';

Map<String, Object?> _card(String module, int order, String front) => {
  'module': module,
  'order': order,
  'front': front,
  'back': 'The answer to "$front", in at most thirty words.',
  'source': 'https://en.wikipedia.org/wiki/Four-stroke_engine',
  'excerpt':
      'The four strokes are intake, compression, combustion and exhaust, '
      'repeated twice per crankshaft revolution pair.',
  'rev': 1,
  'origin': 'generated',
};

Map<String, Object?> _module(
  String id,
  String title,
  String status, {
  List<String> requires = const [],
  double recall = 0,
  int cards = 0,
}) => {
  'id': id,
  'title': title,
  'summary': 'What $title covers, in one or two sentences.',
  'requires': requires,
  'depth': 1,
  'status': status,
  'recall': recall,
  'cards': cards,
};

String _day(DateTime d) => d.toIso8601String().substring(0, 10);

/// The fixture tree under `tutor/v1`, relative to [now] (ms).
Map<String, Object?> fixtureTree(int now) {
  const day = 86400000;
  return {
    'meta': {'schema': 1, 'min_client': 1},
    'rev': {'catalog': 7, 'stats': 3},
    'prefs': {'current_subject': 'car'},
    'live': {
      'session': fixtureLiveSid,
      'subject': 'car',
      'card': 'eng-strokes',
    },
    'presence': {
      'workers': {
        'w': {
          'host': 'pc',
          'pid': 1,
          'version': '1',
          'started': now,
          'beat': now,
        },
      },
    },
    'stats': {
      'today': {
        'day': '2026-10-12',
        'credited_minutes': 23,
        'active_minutes': 31,
        'target': 60,
        'new': 4,
        'new_cap': 10,
      },
      'days': {
        for (var i = 13; i >= 0; i--)
          _day(DateTime.utc(2026, 10, 12 - i)): {
            'minutes': (i * 7) % 61,
            'taught': i % 3,
            'reviews': (i * 5) % 17,
          },
      },
    },
    'subjects': {
      'car': {
        'meta': {
          'title': 'How a car works',
          'goal': 'I want to learn how a car works',
          'status': 'active',
          'created': now - 3 * day,
          'plan_rev': 2,
          'rev': 4,
          'origin': 'generated',
        },
        'plan': {
          'rev': 2,
          'status': 'approved',
          'notes': 'Engine first: everything else is driven by it.',
          'modules': [
            _module(
              'engine',
              'The four-stroke engine',
              'mastered',
              recall: 0.85,
              cards: 3,
            ),
            _module(
              'fuel',
              'Fuel and ignition',
              'ready',
              requires: ['engine'],
              recall: 0.33,
              cards: 3,
            ),
            _module(
              'drivetrain',
              'Clutch, gearbox, drivetrain',
              'locked',
              requires: ['engine'],
            ),
            _module('brakes', 'Brakes', 'failed', requires: ['drivetrain']),
          ],
        },
        'cards': {
          'eng-strokes': _card('engine', 1, 'What are the four strokes?'),
          'eng-crank': _card('engine', 2, 'What does the crankshaft do?'),
          'eng-valves': _card('engine', 3, 'What opens the valves?'),
          'fuel-spark': _card('fuel', 1, 'What ignites the mixture?'),
        },
        'concepts': [
          {'name': 'intake stroke', 'at': now - day},
          {'name': 'compression ratio', 'at': now - day},
        ],
      },
      'garden': {
        'meta': {
          'title': 'Vegetable gardening',
          'goal': 'I want to grow vegetables on a balcony',
          'status': 'draft',
          'created': now - day,
          'plan_rev': 1,
          'rev': 1,
          'origin': 'generated',
        },
        'plan': {
          'rev': 1,
          'status': 'draft',
          'notes': 'Soil and light come before choosing plants.',
          'modules': [
            _module('light', 'Light and orientation', 'locked'),
            _module('soil', 'Soil and containers', 'locked'),
            _module('water', 'Watering', 'locked', requires: ['soil']),
            _module(
              'plants',
              'Choosing plants',
              'locked',
              requires: ['light', 'soil'],
            ),
          ],
        },
      },
    },
    ...fixtureSessions(now),
  };
}

/// Cards taught a month ago (so they are due for review now).
const fixtureTaught = ['eng-strokes', 'eng-crank', 'eng-valves'];
