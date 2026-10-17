import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/session/answers.dart';

void main() {
  const m = Message(
    role: 'tutor',
    text: 't',
    questions: ['Why?', 'How?'],
    check: {'question': 'What is a rung?', 'concept': 'rung'},
  );

  test('questions then the check, numbered on', () {
    final asked = askedOf(m);
    expect(asked.map((a) => a.label), ['Q1', 'Q2', 'Q3']);
    expect(asked.last.check, isTrue);
    expect(asked.last.heading, 'Q3 - Comprehension check');
    expect(asked.first.heading, 'Q1');
  });

  test('a blank or missing check adds no box', () {
    expect(
      askedOf(const Message(role: 'tutor', text: '', check: {'question': ' '})),
      isEmpty,
    );
    expect(askedOf(const Message(role: 'tutor', text: '')), isEmpty);
  });

  test('compose: skipped, trailing space only cut, no comment', () {
    final asked = askedOf(m);
    expect(composeAnswers(asked, ['', ' ', '', '']), '');
    // An old draft's extra comment entry is ignored, never sent.
    expect(composeAnswers(asked, ['', '', '', 'stale comment']), '');
    expect(
      composeAnswers(asked, ['  indented  ', '', 'x', 'thanks ']),
      'Q1: Why?\nA:   indented\n\n'
      'Q2: How?\nA: (skipped)\n\n'
      'Q3: What is a rung?\nA: x',
    );
    expect(
      composeAnswers(asked, ['a']),
      'Q1: Why?\nA: a\n\n'
      'Q2: How?\nA: (skipped)\n\nQ3: What is a rung?\nA: (skipped)',
    );
  });

  test('choices follow the questions; the check has its own', () {
    Message withCheck(Object? checkChoices) => Message(
      role: 'tutor',
      text: 't',
      questions: const ['Why?', 'How?'],
      choices: const [
        ['a', 'b', 'c'],
        [],
        ['stray', 'extra', 'row'],
      ],
      check: {'question': 'What is a rung?', 'choices': checkChoices},
    );
    expect(askedOf(withCheck(null)).map((a) => a.choices), [
      ['a', 'b', 'c'],
      <String>[],
      <String>[], // RTDB dropped the check's empty list; no stray row
    ]);
    expect(askedOf(withCheck(['x', ' ', 'y'])).last.choices, ['x', 'y']);
    expect(
      askedOf(withCheck({'1': 'q', '0': 'p', '2': 'r'})).last.choices,
      ['p', 'q', 'r'], // keyed by index, as RTDB may return it
    );
    expect(askedOf(m).first.choices, isEmpty); // an old message
    expect(askedOf(m).last.choices, isEmpty);
  });

  test('compose: an unedited tapped choice is marked, an edited one not', () {
    const tapped = Message(
      role: 'tutor',
      text: 't',
      questions: ['Why?'],
      choices: [
        ['a', 'b', 'c'],
      ],
      check: {
        'question': 'What is a rung?',
        'choices': ['one line', 'a coil', 'a wire'],
      },
    );
    final asked = askedOf(tapped);
    expect(
      composeAnswers(asked, ['a ', 'one line']),
      'Q1: Why?\nA: a $pickedMarker\n\n'
      'Q2: What is a rung?\nA: one line $pickedMarker',
    );
    expect(
      composeAnswers(asked, ['ab', 'one line, I think']),
      'Q1: Why?\nA: ab\n\nQ2: What is a rung?\nA: one line, I think',
    );
  });

  test('draft keys', () {
    expect(answersDraftKey('s', 'm0001'), 'draft.answers.s.m0001');
    expect(plainDraftKey('s'), 'draft.text.s');
  });
}
