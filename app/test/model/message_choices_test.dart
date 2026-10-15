import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/model/request_body.dart';

void main() {
  test('device rides on message, session_start and next only', () {
    for (final b in [
      RequestBody.message('s', 'hi'),
      RequestBody.sessionStart(subject: 'car', resume: true),
      RequestBody.next('s'),
    ]) {
      expect(b.body.containsKey('device'), isFalse);
      final tagged = b.withDevice('phone');
      expect(tagged.kind, b.kind);
      expect(tagged.body, {...b.body, 'device': 'phone'});
    }
    expect(RequestBody.message('s', 'hi').withDevice('desktop').body, {
      'session': 's',
      'text': 'hi',
      'device': 'desktop',
    });
    // Other kinds are returned as they are.
    final stop = RequestBody.stop('s');
    expect(stop.withDevice('phone'), same(stop));
    expect(RequestBody.drillNext().withDevice('phone').body.keys, ['subject']);
  });

  group('Message.choices', () {
    Message parse(Object? choices) => Message.fromJson({
      'role': 'tutor',
      'text': 't',
      'questions': ['a', 'b'],
      'choices': ?choices,
    });

    test('missing field = none; round-trips when present', () {
      expect(parse(null).choices, isEmpty);
      expect(parse(null).toJson().containsKey('choices'), isFalse);
      final m = parse([
        ['x', 'y', 'z'],
        <String>[],
      ]);
      expect(m.choices, [
        ['x', 'y', 'z'],
        <String>[],
      ]);
      expect(Message.fromJson(m.toJson()).choices, m.choices);
    });

    test(
      'RTDB drops empty lists: gaps, nulls and keyed objects read as []',
      () {
        // [[], [a,b,c], []] stored: only index 1 survives.
        final keyed = parse({
          '1': ['a', 'b', 'c'],
        });
        expect(keyed.choices, [
          <String>[],
          ['a', 'b', 'c'],
        ]);
        // A null entry, a short list (missing trailing indices).
        final nulls = parse([
          null,
          ['a', 'b', 'c'],
        ]);
        expect(nulls.choices, [
          <String>[],
          ['a', 'b', 'c'],
        ]);
        // Missing for question 2 entirely: askedOf gives [] (see answers_test).
        expect(
          parse([
            ['x'],
          ]).choices,
          [
            ['x'],
          ],
        );
        // An inner object keyed by index (a dropped string in the middle).
        expect(
          parse([
            {'0': 'a', '2': 'c'},
          ]).choices,
          [
            ['a', 'c'],
          ],
        );
        // Negative / non-numeric keys are ignored.
        expect(
          parse({
            'x': ['a'],
            '-1': ['b'],
          }).choices,
          isEmpty,
        );
      },
    );

    test('malformed entries read as no choices, never an error', () {
      expect(parse('nope').choices, isEmpty);
      expect(
        parse([
          'str',
          ['ok', 3, ' ', null],
        ]).choices,
        [
          <String>[],
          ['ok'],
        ],
      );
      expect(
        parse([<String>[], <String>[]]).toJson().containsKey('choices'),
        isFalse,
      );
    });
  });
}
