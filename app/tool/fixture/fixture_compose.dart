/// The composer demo: a tutor message with three questions, each with three
/// tap-to-fill choices (`?compose=1` in the fixture build; also what the
/// composer widget tests answer).
library;

/// Its key under the live session's `msgs`.
const fixtureComposeKey = 'm0005';

/// The message, relative to [now] (ms).
Map<String, Object?> fixtureComposeMsg(int now) => {
  'role': 'tutor',
  'text':
      'Good. Now three quick ones on the **cycle**:\n\n'
      '- the valves open and close on a schedule\n'
      '- the crankshaft turns twice per cycle\n\n'
      'Answer in your own words; a guess is fine.',
  'questions': [
    'Which stroke makes the power?',
    'Why does the crankshaft turn twice per cycle?',
    'What closes the valves again after they open?',
  ],
  'choices': [
    ['The power stroke', 'The intake stroke', 'The exhaust stroke'],
    [
      'Four strokes, two per turn',
      'The piston goes up twice',
      'It needs a second spark',
    ],
    ['Valve springs', 'The camshaft lobe', 'The spark plug'],
  ],
  'at': now - 60000,
};

/// A comprehension check with its own choices: the composer tests add it to
/// the message and tap one, which is sent with `(picked option)`.
const fixtureComposeCheck = <String, Object?>{
  'question': 'What turns the piston push into rotation?',
  'concept': 'crankshaft',
  'choices': ['The crankshaft', 'The camshaft', 'The flywheel'],
};
