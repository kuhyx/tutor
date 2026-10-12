import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/editor/card_rules.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/relay/error_text.dart';

void main() {
  test('word counts and problems', () {
    expect(wordCount('  a  b\nc '), 3);
    expect(wordCount(''), 0);
    expect(
      cardProblems(
        front: 'What is a rung?',
        back: 'One line of ladder logic.',
        source: 'https://example.org/x',
        excerpt: 'one two three four five six',
      ),
      isEmpty,
    );
    final bad = cardProblems(
      front: '',
      back: 'w ' * 31,
      source: 'http://example.org',
      excerpt: 'too short',
    );
    expect(bad, hasLength(4));
    expect(
      cardProblems(front: 'a', back: 'b', source: '::', excerpt: 'w ' * 41),
      hasLength(2),
    );
  });

  test('host of a link', () {
    expect(hostOf('https://en.wikipedia.org/wiki/X'), 'en.wikipedia.org');
    expect(hostOf('nonsense'), 'nonsense');
  });

  test('phase text for every phase', () {
    expect(Phase.values.map(phaseText).toSet(), hasLength(Phase.values.length));
  });
}
