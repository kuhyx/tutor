// The model's trace (DOCS-contract §6 STEP): a message's `trace` list and
// the live `progress` node, read forgivingly; adjacent thinking concatenates.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/model/trace.dart';

void main() {
  test('a list of steps parses in order; adjacent thinking joins', () {
    final steps = parseTrace([
      {'kind': 'thinking', 'text': 'Check '},
      {'kind': 'thinking', 'text': 'the codes.'},
      {'kind': 'tool', 'name': 'WebSearch', 'input': 'modbus codes'},
      'junk',
      {'kind': 'other'},
      {'kind': 'thinking', 'text': 'Done.'},
    ]);
    expect(steps.map((s) => s.kind), ['thinking', 'tool', 'thinking']);
    expect(steps[0].text, 'Check the codes.');
    expect(steps[1].name, 'WebSearch');
    expect(steps[1].input, 'modbus codes');
    expect(steps[2].text, 'Done.');
    expect(parseTrace(null), isEmpty);
    expect(parseTrace('x'), isEmpty);
  });

  test('a keyed node (RTDB) parses in key order', () {
    final steps = parseTrace({
      's0003': {'kind': 'tool', 'name': 'Bash', 'input': 'ls'},
      's0001': {'kind': 'thinking', 'text': 'a'},
      's0002': {'kind': 'thinking', 'text': 'b'},
    });
    expect(steps, hasLength(2));
    expect(steps.first.text, 'ab');
    expect(steps.last.input, 'ls');
  });

  test('a message carries its trace and writes it back', () {
    final m = Message.fromJson({
      'role': 'tutor',
      'text': 'hi',
      'trace': [
        {'kind': 'thinking', 'text': 'Think.'},
        {'kind': 'tool', 'name': 'WebFetch', 'input': 'https://x.org'},
      ],
    });
    expect(m.trace, hasLength(2));
    expect(m.toJson()['trace'], [
      {'kind': 'thinking', 'text': 'Think.'},
      {'kind': 'tool', 'name': 'WebFetch', 'input': 'https://x.org'},
    ]);
    final plain = Message.fromJson({'role': 'tutor', 'text': 'hi'});
    expect(plain.trace, isEmpty);
    expect(plain.toJson().containsKey('trace'), isFalse);
  });

  test('the progress node: its rid and steps; anything else is null', () {
    final p = LiveProgress.parse({
      'rid': '01M4RBCX52MMHCK7K73E6KV910',
      'steps': {
        's0001': {'kind': 'tool', 'name': 'WebSearch', 'input': 'coil'},
      },
    });
    expect(p!.rid, '01M4RBCX52MMHCK7K73E6KV910');
    expect(p.steps.single.input, 'coil');
    expect(LiveProgress.parse(null), isNull);
    expect(LiveProgress.parse({'steps': <String, Object?>{}}), isNull);
    expect(LiveProgress.parse({'rid': 'r'})!.steps, isEmpty);
  });
}
