/// Widget-test helpers for the composer: the live session with the
/// 3-question tutor message as its latest turn.
library;

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/session/session_screen.dart';
import 'package:tutor/util/device.dart';

import '../../tool/fixture/fixture_compose.dart';
import '../../tool/fixture/fixture_sessions.dart';
import 'fake_rtdb.dart';
import 'fake_stream.dart';
import 'ui.dart';

const composeBase = 'tutor/v1/sessions/$fixtureLiveSid';
const _phoneSize = Size(412, 915);

/// Opens the live session with the 3-question message as the latest turn.
Future<(FakeRtdb, FakeStream)> openComposer(
  WidgetTester t, {
  required bool phone,
  Size? size,
  List<String>? draft,
  bool questions = true,
  bool check = false,
}) async {
  debugPhone = phone;
  final db = fixtureDb();
  final msg = fixtureComposeMsg(fixtureNow);
  if (check) msg['check'] = fixtureComposeCheck;
  if (!questions) {
    msg
      ..remove('questions')
      ..remove('choices');
  }
  db.root = setAt(db.root, '$composeBase/msgs/$fixtureComposeKey', msg);
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  if (draft != null) {
    await s.kv.set(
      answersDraftKey(fixtureLiveSid, fixtureComposeKey),
      jsonEncode(draft),
    );
  }
  await pumpScreen(
    t,
    SessionScreen(services: s, now: () => DateTime(2030)),
    size: size ?? (phone ? _phoneSize : const Size(1366, 900)),
    settle: false,
  );
  for (final path in [
    'tutor/v1/live',
    '$composeBase/meta',
    '$composeBase/msgs',
  ]) {
    stream.listens[path]?.add(RtdbPut('/', getAt(db.root, path)));
    await t.pump();
  }
  await t.pumpAndSettle();
  return (db, stream);
}

// The tutor text is rich text (markdown spans).
Finder rich(String s) => find.textContaining(s, findRichText: true);

String boxText(WidgetTester t) =>
    t.widget<TextField>(find.byType(TextField)).controller!.text;
