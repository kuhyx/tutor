// The answer boxes while a turn is in flight: always typeable, only Send,
// Ctrl+Enter and Hint wait; a late draft load or a rebuild for the same
// question never drops what was typed.
import 'dart:async';
import 'dart:convert';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/ui/session/composer.dart';

const _sid = '20261017-120000-abcd';

KeyedMessage _msg(String key, List<String> questions) => KeyedMessage(
  key,
  Message(
    role: 'tutor',
    text: 't',
    questions: questions,
    choices: const [
      ['a', 'b'],
    ],
  ),
);

/// A store whose draft read resolves only when the test says so.
class _SlowKv extends MemoryKv {
  final reads = <Completer<String?>>[];

  @override
  Future<String?> get(String key) {
    final c = Completer<String?>();
    reads.add(c);
    return c.future;
  }
}

Future<List<String>> _pump(
  WidgetTester t, {
  required KeyedMessage latest,
  required KvStore kv,
  bool enabled = true,
  bool phone = false,
}) async {
  final sent = <String>[];
  await t.pumpWidget(
    MaterialApp(
      theme: buildLightTheme(),
      home: Scaffold(
        body: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Composer(
              sid: _sid,
              latest: latest,
              kv: kv,
              enabled: enabled,
              onSend: (text) async {
                sent.add(text);
                return true;
              },
              phone: phone,
            ),
          ],
        ),
      ),
    ),
  );
  await t.pump();
  return sent;
}

String _box(WidgetTester t, int i) =>
    t.widget<TextField>(find.byType(TextField).at(i)).controller!.text;

VoidCallback? _chip(WidgetTester t, String label) => t
    .widget<ActionChip>(find.widgetWithText(ActionChip, label).first)
    .onPressed;

void main() {
  testWidgets('busy: boxes typeable; Send, Ctrl+Enter, Hint wait', (t) async {
    final kv = MemoryKv();
    final msg = _msg('m0001', ['Why?', 'How?']);
    final sent = await _pump(t, latest: msg, kv: kv, enabled: false);
    final boxes = find.byType(TextField);
    expect(t.widget<TextField>(boxes.at(0)).readOnly, isFalse);
    await t.tap(boxes.at(1));
    await t.enterText(boxes.at(1), 'typed while busy');
    await t.pump();
    expect(_box(t, 1), 'typed while busy');
    final send = find.widgetWithText(FilledButton, 'Send');
    expect(t.widget<FilledButton>(send).onPressed, isNull);
    expect(_chip(t, 'Hint'), isNull);
    expect(_chip(t, 'a'), isNotNull); // a choice only fills the box
    await t.tap(find.text('a'));
    await t.pump();
    expect(_box(t, 0), 'a');
    await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await t.sendKeyEvent(LogicalKeyboardKey.enter);
    await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await t.pump();
    expect(sent, isEmpty);

    await _pump(t, latest: msg, kv: kv); // the turn is over
    expect(_box(t, 1), 'typed while busy');
    expect(t.widget<FilledButton>(send).onPressed, isNotNull);
  });

  testWidgets('a late draft load never clobbers typed text', (t) async {
    final kv = _SlowKv();
    await _pump(t, latest: _msg('m0001', ['Why?', 'How?']), kv: kv);
    await t.enterText(find.byType(TextField).at(0), 'fresh');
    kv.reads.single.complete(jsonEncode(['old one', 'old two']));
    await t.pump();
    expect(_box(t, 0), 'fresh');
    expect(_box(t, 1), 'old two'); // an untouched box still gets its draft
  });

  testWidgets('phone: typing before the draft keeps the step', (t) async {
    final kv = _SlowKv();
    await _pump(
      t,
      latest: _msg('m0001', ['Why?', 'How?']),
      kv: kv,
      phone: true,
    );
    expect(find.text('1/2'), findsOneWidget);
    await t.enterText(find.byType(TextField), 'fresh');
    kv.reads.single.complete(jsonEncode(['', '']));
    await t.pump();
    expect(find.text('1/2'), findsOneWidget);
    expect(_box(t, 0), 'fresh');
  });

  testWidgets('a rebuild for the same question keeps typed text', (t) async {
    final kv = MemoryKv();
    await _pump(t, latest: _msg('m0001', ['Why?', 'How?']), kv: kv);
    await t.enterText(find.byType(TextField).at(1), 'mine');
    await _pump(t, latest: _msg('m0003', ['Why?', 'How?']), kv: kv);
    await t.pump();
    expect(_box(t, 1), 'mine');
    await _pump(t, latest: _msg('m0005', ['Other?']), kv: kv);
    await t.pump();
    expect(_box(t, 0), '');
  });
}
