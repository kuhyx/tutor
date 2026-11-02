import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/mock/mock_links.dart';
import 'package:tutor/mock/mock_queue.dart';
import 'package:tutor/mock/mock_session.dart';
import 'package:tutor/mock/mock_test_screen.dart';
import 'package:tutor/storage/kv_store.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/services.dart';
import '../support/ui.dart';
import 'mock_fixtures.dart';

const phone = Size(412, 915);

class Rig {
  new() : db = FakeRtdb(), stream = FakeStream() {
    kv = MemoryKv();
    s = services(db, stream, kv: kv);
  }

  final FakeRtdb db;
  final FakeStream stream;
  late final MemoryKv kv;
  late final TutorServices s;
  int clock = 1000000 + 60000;
  final opened = <String>[];

  late final MockLinks links = (
    openLesson: (c, topic) async => opened.add('lesson:$topic'),
    openCoach: (c, slug) async => opened.add('coach:$slug'),
  );

  MockSession session({Map<String, dynamic>? paper}) => MockSession.begin(
    kv,
    MockAnswerQueue(kv),
    relayAnswerSender(s.relay),
    paper ?? paperData,
    now: () => clock,
  );

  Future<MockSession> pumpTest(
    WidgetTester t, {
    MockSession? session,
    bool settle = true,
  }) async {
    final m = session ?? this.session();
    await pumpScreen(
      t,
      MockTestScreen(services: s, session: m, links: links),
      size: phone,
      settle: settle,
    );
    return m;
  }
}
