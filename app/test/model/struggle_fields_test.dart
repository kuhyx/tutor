// DOCS-contract-struggle.md §1/§4: the card's `mnemonic` and `split_of`,
// `session_start` `struggle: true`, and the Editor's `card_edit` mnemonic.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/editor/card_rules.dart';
import 'package:tutor/model/card.dart';
import 'package:tutor/model/request_body.dart';

const Map<String, Object> _base = {
  'module': 'm',
  'order': 1,
  'front': 'Q?',
  'back': 'A.',
  'source': 'https://example.com',
  'excerpt': 'some verbatim words from the source page',
  'rev': 2,
  'origin': 'edited',
};

void main() {
  test('a card parses and writes mnemonic and split_of', () {
    final card = StudyCard.fromJson({
      ..._base,
      'mnemonic': 'Crank turns up-down into round',
      'split_of': 'eng-old',
    });
    expect(card.mnemonic, 'Crank turns up-down into round');
    expect(card.splitOf, 'eng-old');
    expect(card.toJson(), containsPair('mnemonic', card.mnemonic));
    expect(card.toJson(), containsPair('split_of', 'eng-old'));
    final plain = StudyCard.fromJson(_base);
    expect(plain.mnemonic, isNull);
    expect(plain.splitOf, isNull);
    expect(plain.toJson().containsKey('mnemonic'), isFalse);
  });

  test('session_start carries struggle: true, also through a cap lift', () {
    final body = RequestBody.sessionStart(
      subject: 'car',
      card: 'eng-crank',
      struggle: true,
    );
    expect(body.body, containsPair('struggle', true));
    expect(body.body, containsPair('card', 'eng-crank'));
    expect(body.liftingCap()!.body, containsPair('struggle', true));
    expect(RequestBody.sessionStart().body.containsKey('struggle'), isFalse);
  });

  test('card_edit sends the mnemonic; empty clears it', () {
    RequestBody edit({String mnemonic = ''}) => RequestBody.cardEdit(
      subject: 's',
      module: 'm',
      front: 'f',
      back: 'b',
      source: 'https://x.org',
      excerpt: 'e',
      mnemonic: mnemonic,
    );
    expect(edit(mnemonic: 'Ring').body, containsPair('mnemonic', 'Ring'));
    expect(edit().body, containsPair('mnemonic', ''));
  });

  test('the Editor checks the mnemonic: <= 40 words, one line', () {
    List<String> problems(String m) => cardProblems(
      front: 'Q?',
      back: 'A.',
      source: 'https://example.com',
      excerpt: 'some verbatim words from the source page',
      mnemonic: m,
    );
    expect(problems(''), isEmpty);
    expect(problems(List.filled(kMnemonicWords, 'w').join(' ')), isEmpty);
    expect(
      problems(List.filled(kMnemonicWords + 1, 'w').join(' ')).single,
      startsWith('Mnemonic:'),
    );
    expect(problems('two\nlines').single, startsWith('Mnemonic:'));
  });
}
