/// The tutor's thinking in the fixture: `&trace=1` gives the live session's
/// last tutor turn (m0004) a trace (the folded Thinking panel), `&busy=1`
/// puts a turn in flight with research under way (`meta.busy` + `progress`),
/// `&open=1` opens every Thinking panel.
library;

import 'package:tutor/sync/json_tree.dart';

import 'fixture_sessions.dart' show fixtureLiveSid;

const _base = 'tutor/v1/sessions/$fixtureLiveSid';
const _rid = '01M4RBCX52MMHCK7K73E6KV9ZZ';

const _trace = <Map<String, String>>[
  {
    'kind': 'thinking',
    'text':
        'The learner named the piston. Next: the four strokes. Check the '
        'order of the strokes before asking which one makes the power.',
  },
  {'kind': 'tool', 'name': 'WebSearch', 'input': 'four-stroke engine cycle'},
  {
    'kind': 'tool',
    'name': 'WebFetch',
    'input': 'https://en.wikipedia.org/wiki/Four-stroke_engine',
  },
  {
    'kind': 'thinking',
    'text':
        'Confirmed: intake, compression, power, exhaust; two crank turns. '
        'Show the animation and ask about the power stroke.',
  },
];

const _progress = <String, Map<String, String>>{
  's0001': {
    'kind': 'thinking',
    'text':
        'The learner says the spark pushes the piston. Is that the whole '
        'story? Look up what the compression stroke adds.',
  },
  's0002': {
    'kind': 'tool',
    'name': 'WebSearch',
    'input': 'why compress the mixture before ignition',
  },
  's0003': {
    'kind': 'tool',
    'name': 'WebFetch',
    'input': 'https://en.wikipedia.org/wiki/Compression_ratio',
  },
  's0004': {
    'kind': 'thinking',
    'text': ' Higher compression, more work per stroke. ',
  },
  's0005': {
    'kind': 'tool',
    'name': 'Bash',
    'input': 'python3 otto_cycle.py 10',
  },
};

/// [root] with m0004's trace, in the live session and in the stopped copy
/// History opens (`20261011-090000-a1b2`).
Object? fixtureWithTrace(Object? root) => setAt(
  setAt(root, '$_base/msgs/m0004/trace', _trace),
  'tutor/v1/sessions/20261011-090000-a1b2/msgs/m0004/trace',
  _trace,
);

/// [root] with a turn in flight: the learner's text pending, research
/// steps so far in `progress`.
Object? fixtureInFlight(Object? root, int now) {
  final busy = {
    'rid': _rid,
    'phase': 'thinking',
    'since': now - 25000,
    'text': 'The spark pushes the piston down.',
  };
  final next = setAt(root, '$_base/meta/busy', busy);
  return setAt(next, '$_base/progress', {'rid': _rid, 'steps': _progress});
}
