import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/coach/coach_models.dart';

import 'coach_fixtures.dart';

void main() {
  test('a run report: examples, errors, SQL rows', () {
    final r = parseRunReport(runData);
    expect((r.ok, r.passed, r.total, r.held), (false, 1, 3, false));
    expect(r.examples.map((e) => e.ok), [true, false, false]);
    expect((r.examples[1].got, r.examples[1].expected), ('[1,2]', '[0,2]'));
    expect(r.examples[2].error, 'TypeError');
    expect(r.examples[2].rows, isEmpty);
    final s = parseRunReport(sqlRunData);
    final e = s.examples.single;
    expect(e.columns, ['id', 'Jan']);
    expect(e.rows[1], ['2', 'NULL']);
    expect(e.expectedRows[1], ['2', '5']);
    expect((e.diff.single.row, e.diff.single.col), (1, 1));
    expect((e.diff.single.expected, e.diff.single.actual), ('5', 'NULL'));
    expect((s.passed, s.total), (0, 1));
    final b = parseRunReport(const {
      'error': 'timeout',
      'no_examples': true,
      'held': true,
      'note': 'Gate first',
    });
    expect(
      (b.error, b.noExamples, b.held, b.note),
      ('timeout', true, true, 'Gate first'),
    );
    expect(
      () => parseRunReport(const {
        'examples': [3],
      }),
      throwsFormatException,
    );
    expect(
      () => parseRunReport(const {
        'examples': [
          {
            'cell_diff': [
              [1],
            ],
          },
        ],
      }),
      throwsFormatException,
    );
  });

  test('cards: made, proposed, refused, the Anki line', () {
    final c = parseCoachCards(cardsData);
    expect(
      (c.cards.single.id, c.cards.single.back, c.cards.single.isNew),
      ('hash-lookup', 'hash map', true),
    );
    expect(c.proposals.map((e) => e.name), [
      'conditional aggregation',
      'quoting',
    ]);
    expect(c.proposals.first.aliases, ['sum case']);
    expect(c.proposals.last.aliases, isEmpty);
    expect(c.proposals.last.properties, ['text value vs identifier']);
    expect(
      (c.refused.single.name, c.refused.single.reason),
      ('nest', 'nests with hash map'),
    );
    expect(c.ankiLine, 'Anki is closed');
    final none = parseCoachCards(const {});
    expect(none.cards, isEmpty);
    expect(none.proposals, isEmpty);
    expect(none.refused, isEmpty);
    expect((none.ankiLine, none.state), (null, null));
    final bare = parseCoachCards(const {
      'cards': [
        {'id': 'x'},
      ],
      'refused': [
        {'name': 'n'},
      ],
      'anki': <String, Object?>{},
    });
    expect(
      (bare.cards.single.front, bare.refused.single.reason, bare.ankiLine),
      ('', '', null),
    );
  });
}
