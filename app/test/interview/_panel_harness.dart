/// A Focus screen over fakes, for the interview panel tests.
library;

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/focus_screen.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/services.dart';
import '../support/ui.dart';
import '_data.dart';
import '_fakes.dart';

/// A milestone block as a result carries it.
Map<String, Object?> block(List<Map<String, Object>> milestones) => {
  'milestones': milestones,
  'missed': false,
  'trips': <Object>[],
  'weekend_answers': <String, Object>{},
};

/// The screen, its fake DB and stream, scripted prompts and picked image.
class PanelHarness {
  late FakeRtdb db;
  late FakeStream stream;
  late FakePrompts prompts;
  Uint8List? picked;

  /// Opens the screen and answers `focus_status` with [project].
  Future<void> open(WidgetTester t, Map<String, Object?> project) async {
    db = FakeRtdb();
    stream = FakeStream();
    prompts = FakePrompts();
    picked = fakePng;
    final s = services(db, stream);
    addTearDown(s.focus.dispose);
    await pumpScreen(
      t,
      FocusScreen(services: s, prompts: prompts, pickImage: () async => picked),
      settle: false,
    );
    await answer(t, db, stream, data: statusOf(project));
  }

  /// The icon of milestone slot [name].
  Finder key(String name) => find.byKey(ValueKey('ms:$name'));

  /// The colour of that icon.
  Color? colorOf(WidgetTester t, String name) => t
      .widget<Icon>(
        find.descendant(of: key(name), matching: find.byType(Icon)).first,
      )
      .color;

  /// Body of the latest request.
  Map<String, dynamic> lastBody() =>
      lastRequest(db).$2['body'] as Map<String, dynamic>;

  /// Kind of the latest request.
  String lastKind() => lastRequest(db).$2['kind'] as String;
}
