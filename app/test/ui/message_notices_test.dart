// The tutor's card edits show as notice lines on its message
// ("Card removed: <front>"), read from the message's `notices`.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/ui/session/message_tile.dart';

void main() {
  testWidgets('card edit notices render under the tutor text', (t) async {
    final m = Message.fromJson({
      'role': 'tutor',
      'text': 'Fair point, I removed that card.',
      'notices': [
        'Card removed: What is a coil?',
        'Card added: What is a relay?',
      ],
    });
    await t.pumpWidget(
      MaterialApp(
        home: Scaffold(body: MessageTile(message: m)),
      ),
    );
    expect(m.notices, hasLength(2));
    expect(find.text('Card removed: What is a coil?'), findsOneWidget);
    expect(find.text('Card added: What is a relay?'), findsOneWidget);
  });

  test('no notices: none written back', () {
    final m = Message.fromJson({'role': 'tutor', 'text': 'hi'});
    expect(m.notices, isEmpty);
    expect(m.toJson().containsKey('notices'), isFalse);
  });
}
