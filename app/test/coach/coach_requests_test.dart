import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/coach/coach_requests.dart';
import 'package:tutor/model/request.dart';

void main() {
  test('every lc kind is on the chat lane with its wire name', () {
    final kinds = {
      RequestKind.lcList: 'lc_list',
      RequestKind.lcOpen: 'lc_open',
      RequestKind.lcTurn: 'lc_turn',
      RequestKind.lcRun: 'lc_run',
      RequestKind.lcCards: 'lc_cards',
    };
    for (final e in kinds.entries) {
      expect(e.key.wire, e.value);
      expect(e.key.lane, Lane.chat);
      expect(RequestKind.parse(e.value), e.key);
    }
  });

  test('bodies carry exactly the worker fields', () {
    expect(lcList().body, isEmpty);
    expect(lcOpen(problem: 'two-sum', lang: 'python3').body, {
      'problem': 'two-sum',
      'lang': 'python3',
    });
    expect(lcOpen(statement: 'S', title: 'T').body, {
      'statement': 'S',
      'title': 'T',
    });
    expect(lcOpen(lcId: 'abc').body, {'lc_id': 'abc'});
    expect(lcTurn('i', 'hello').body, {
      'lc_id': 'i',
      'text': 'hello',
      'intent': 'chat',
    });
    expect(lcTurn('i', 'because', solved: true).body['intent'], 'solved');
    expect(lcRun('i', lang: 'mysql', code: 'SELECT 1').body, {
      'lc_id': 'i',
      'lang': 'mysql',
      'code': 'SELECT 1',
    });
  });

  test('cards without entries only asks', () {
    expect(lcCards('i', const []).body, {'lc_id': 'i'});
  });

  test('cards: aliases only when there are some', () {
    final body = lcCards('i', [
      (name: 'a', aliases: ['b'], properties: ['p']),
      (name: 'c', aliases: <String>[], properties: ['q']),
    ]).body;
    expect(body['confirm'], [
      {
        'name': 'a',
        'aliases': ['b'],
        'properties': ['p'],
      },
      {
        'name': 'c',
        'properties': ['q'],
      },
    ]);
  });

  test('open needs a problem, a statement or a session', () {
    expect(() => lcOpen(lang: 'mysql'), throwsArgumentError);
  });
}
