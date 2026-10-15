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

  test('compose: skipped, comment, trailing space only cut', () {
    final asked = askedOf(m);
    expect(composeAnswers(asked, ['', ' ', '', '']), '');
    expect(
      composeAnswers(asked, ['  indented  ', '', 'x', 'thanks ']),
      'Q1: Why?\nA:   indented\n\n'
      'Q2: How?\nA: (skipped)\n\n'
      'Q3: What is a rung?\nA: x\n\n'
      'Comment: thanks',
    );
    expect(
      composeAnswers(asked, ['a']),
      'Q1: Why?\nA: a\n\n'
      'Q2: How?\nA: (skipped)\n\nQ3: What is a rung?\nA: (skipped)',
    );
  });

  test('choices follow the questions; the check has none', () {
    const withChoices = Message(
      role: 'tutor',
      text: 't',
      questions: ['Why?', 'How?'],
      choices: [
        ['a', 'b', 'c'],
        [],
        ['stray', 'extra', 'row'],
      ],
      check: {'question': 'What is a rung?'},
    );
    expect(askedOf(withChoices).map((a) => a.choices), [
      ['a', 'b', 'c'],
      <String>[],
      <String>[],
    ]);
    expect(askedOf(m).first.choices, isEmpty); // an old message
  });

  test('draft keys', () {
    expect(answersDraftKey('s', 'm0001'), 'draft.answers.s.m0001');
    expect(plainDraftKey('s'), 'draft.text.s');
  });
}
