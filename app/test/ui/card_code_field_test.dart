// curriculum §3: a card's optional `code` skeleton, shown as monospace code
// under the answer (review and the focus check-in), sent by the Editor.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/card.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/ui/review_answer.dart';
import 'package:tutor/ui/sql/data_grid.dart';
import 'package:tutor/ui/sql/rich_md.dart';

import '../support/ui.dart';

const _skeleton =
    'function twoSum(nums: number[], target: number): number[] {\n'
    '  const seen = new Map<number, number>();\n'
    '  return [];\n'
    '}';

const Map<String, Object> _base = {
  'module': 'm',
  'order': 1,
  'front': 'Which pattern finds a pair summing to a target?',
  'back': 'A hash map of seen values.',
  'source': 'https://example.com',
  'excerpt': 'some verbatim words from the source page',
  'rev': 1,
  'origin': 'generated',
};

Future<void> _face(WidgetTester t, StudyCard card, {bool revealed = true}) =>
    pumpScreen(
      t,
      Scaffold(
        body: SingleChildScrollView(
          child: SizedBox(
            width: 360,
            child: CardFace(card, revealed: revealed),
          ),
        ),
      ),
    );

void main() {
  test('card_code_field: a card parses and writes its code verbatim', () {
    final card = StudyCard.fromJson({..._base, 'code': _skeleton});
    expect(card.code, _skeleton);
    expect(card.toJson(), containsPair('code', _skeleton));
    final plain = StudyCard.fromJson(_base);
    expect(plain.code, isNull);
    expect(plain.toJson().containsKey('code'), isFalse);
  });

  test('card_code_field: card_edit sends the code; empty clears it', () {
    RequestBody edit({String code = ''}) => RequestBody.cardEdit(
      subject: 's',
      module: 'm',
      front: 'f',
      back: 'b',
      source: 'https://x.org',
      excerpt: 'e',
      code: code,
    );
    expect(edit(code: _skeleton).body, containsPair('code', _skeleton));
    expect(edit().body, containsPair('code', ''));
  });

  testWidgets('card_code_field: the revealed face shows it as monospace', (
    t,
  ) async {
    await _face(t, StudyCard.fromJson({..._base, 'code': _skeleton}));
    expect(find.byType(CodeBlock), findsOneWidget);
    final text = t.widget<SelectableText>(
      find.descendant(
        of: find.byType(CodeBlock),
        matching: find.byType(SelectableText),
      ),
    );
    expect(text.data, _skeleton);
    expect(text.style?.fontFamily, kMonoFamily);
    expect(t.getSize(find.byType(CodeBlock)).width, lessThanOrEqualTo(360));
  });

  testWidgets('card_code_field: no code, or the front only, shows no block', (
    t,
  ) async {
    await _face(t, StudyCard.fromJson(_base));
    expect(find.byType(CodeBlock), findsNothing);
    await _face(t, StudyCard.fromJson({..._base, 'code': ''}));
    expect(find.byType(CodeBlock), findsNothing);
    await _face(
      t,
      StudyCard.fromJson({..._base, 'code': _skeleton}),
      revealed: false,
    );
    expect(find.byType(CodeBlock), findsNothing);
  });
}
