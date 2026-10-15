import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/model/request_body.dart';

void main() {
  test('message carries the device only when given', () {
    expect(RequestBody.message('s', 'hi').body, {'session': 's', 'text': 'hi'});
    expect(RequestBody.message('s', 'hi', device: 'phone').body, {
      'session': 's',
      'text': 'hi',
      'device': 'phone',
    });
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
