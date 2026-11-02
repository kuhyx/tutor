import 'dart:async';

import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/mock/mock_links.dart';
import 'package:tutor/mock/mock_queue.dart';
import 'package:tutor/mock/mock_result_screen.dart';
import 'package:tutor/mock/mock_session.dart';
import 'package:tutor/mock/mock_start_screen.dart';
import 'package:tutor/mock/mock_test_screen.dart';

/// Opens the saved test (running, or its result) or else the start screen.
Future<void> openMock(
  BuildContext context,
  TutorServices s, {
  MockLinks? links,
}) async {
  final wired = links ?? mockRoutes(s);
  final saved = await loadMockSession(
    s.kv,
    MockAnswerQueue(s.kv),
    relayAnswerSender(s.relay),
  );
  if (!context.mounted) return;
  final screen = switch (saved) {
    null => MockStartScreen(services: s, links: wired),
    MockSession(result: != null) => MockResultScreen(
      services: s,
      session: saved,
      links: wired,
    ),
    _ => MockTestScreen(services: s, session: saved, links: wired),
  };
  await Navigator.of(context)
      .push<void>(MaterialPageRoute(builder: (_) => screen));
}
