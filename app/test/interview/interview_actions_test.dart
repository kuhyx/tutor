import 'dart:convert';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';

import '../support/ui.dart';
import '_data.dart';
import '_fakes.dart';
import '_panel_harness.dart';

void main() {
  final h = PanelHarness();

  testWidgets(
    'rules: the h.picked image is chunked, then focus_evidence file',
    (t) async {
      await h.open(t, interviewProject());
      await t.tap(h.key('rules'));
      await sent(t);
      expect(h.lastKind(), 'focus_evidence');
      final body = h.lastBody();
      expect(body['id'], 'acme-interview');
      expect(body['milestone'], 'rules');
      expect(body['kind'], 'file');
      expect(body['mime'], 'image/png');
      expect(body['chunks'], 1);
      expect(body['sha256'], sha256.convert(fakePng).toString());
      final chunk = getAt(
        h.db.root,
        'tutor/v1-e2e/uploads/${body['upload']}/c0001',
      );
      expect(base64Decode(chunk! as String), fakePng);
      // The chunks were written before the request.
      final puts = h.db.log.where((l) => l.startsWith('PUT')).toList();
      expect(
        puts.indexWhere((l) => l.contains('/uploads/')),
        lessThan(puts.lastIndexWhere((l) => l.contains('/requests/'))),
      );

      await answer(
        t,
        h.db,
        h.stream,
        data: block([ms('rules', '2026-11-10T23:59:00', 'done')]),
      );
      expect(h.colorOf(t, 'rules'), AppPalette.success);
    },
  );

  testWidgets('rules: cancelling the picker sends nothing', (t) async {
    await h.open(t, interviewProject());
    final before = lastRequest(h.db).$1;
    h.picked = null;
    await t.tap(h.key('rules'));
    await sent(t);
    expect(lastRequest(h.db).$1, before);
  });

  testWidgets('rules: something that is not an image is refused loudly', (
    t,
  ) async {
    await h.open(t, interviewProject());
    final before = lastRequest(h.db).$1;
    h.picked = Uint8List.fromList(utf8.encode('not a picture at all'));
    await t.tap(h.key('rules'));
    await sent(t);
    expect(lastRequest(h.db).$1, before);
    expect(find.byKey(const ValueKey('interview-error')), findsOneWidget);
  });

  testWidgets('a done milestone is not re-asked', (t) async {
    await h.open(
      t,
      interviewProject(
        milestones: [ms('rules', '2026-11-10T23:59:00', 'done')],
      ),
    );
    final before = lastRequest(h.db).$1;
    await t.tap(h.key('rules'));
    await sent(t);
    expect(lastRequest(h.db).$1, before);
  });

  testWidgets('trip yes: a date range goes out as focus_trip', (t) async {
    await h.open(t, interviewProject());
    h.prompts
      ..trip = true
      ..range = (start: DateTime(2026, 11, 13), end: DateTime(2026, 11, 16));
    await t.tap(h.key('trip'));
    await sent(t);
    expect(h.lastKind(), 'focus_trip');
    expect(h.lastBody(), {
      'id': 'acme-interview',
      'start': '2026-11-13',
      'end': '2026-11-16',
    });
    expect(h.prompts.bounds!.first, DateTime(2026, 11, 10));
    expect(h.prompts.bounds!.last, DateTime(2026, 11, 20));
  });

  testWidgets('trip no: focus_weekend trip:false for the open saturday', (
    t,
  ) async {
    await h.open(t, interviewProject());
    h.prompts.trip = false;
    await t.tap(h.key('trip'));
    await sent(t);
    expect(h.lastKind(), 'focus_weekend');
    expect(h.lastBody(), {
      'id': 'acme-interview',
      'saturday': '2026-11-14',
      'trip': false,
    });
  });

  testWidgets('trip dismissed, or range cancelled: nothing is sent', (t) async {
    await h.open(t, interviewProject());
    final before = lastRequest(h.db).$1;
    await t.tap(h.key('trip'));
    await sent(t);
    h.prompts.trip = true;
    await t.tap(h.key('trip'));
    await sent(t);
    expect(lastRequest(h.db).$1, before);
  });

  testWidgets('phone: a confirmed tap is the offline_ok evidence', (t) async {
    await h.open(t, interviewProject());
    h.prompts.confirmed = true;
    await t.tap(h.key('phone'));
    await sent(t);
    expect(h.lastKind(), 'focus_evidence');
    expect(h.lastBody(), {
      'id': 'acme-interview',
      'milestone': 'phone:2026-11-14',
      'kind': 'tap',
    });
  });

  testWidgets('phone: an unconfirmed tap sends nothing', (t) async {
    await h.open(t, interviewProject());
    final before = lastRequest(h.db).$1;
    await t.tap(h.key('phone'));
    await sent(t);
    expect(lastRequest(h.db).$1, before);
  });

  testWidgets('mock: the score is the evidence', (t) async {
    await h.open(t, interviewProject());
    h.prompts.score = 71.5;
    await t.tap(h.key('mock'));
    await sent(t);
    expect(h.lastBody(), {
      'id': 'acme-interview',
      'milestone': 'mock',
      'kind': 'score',
      'value': 71.5,
    });
  });

  testWidgets('slot: datetime first, then the confirm tap', (t) async {
    await h.open(t, interviewProject());
    h.prompts
      ..dateTime = DateTime(2026, 11, 19, 9, 30)
      ..confirmed = true;
    await t.tap(h.key('slot'));
    await sent(t);
    expect(h.lastBody()['kind'], 'slot');
    expect(h.lastBody()['value'], '2026-11-19T09:30');
    expect(h.prompts.asked['confirm'], isNull, reason: 'not before the answer');
    await answer(
      t,
      h.db,
      h.stream,
      data: block([ms('slot', '2026-11-19T12:00:00', 'pending')]),
      settle: false,
    );
    await sent(t);
    expect(h.lastBody()['kind'], 'slot_confirm');
    expect(h.lastBody()['value'], isTrue);
    expect(h.lastBody()['milestone'], 'slot');
  });

  testWidgets('slot: an unconfirmed entry is confirmed by the next tap', (
    t,
  ) async {
    await h.open(t, interviewProject());
    h.prompts
      ..dateTime = DateTime(2026, 11, 19, 9, 30)
      ..confirmed = null;
    await t.tap(h.key('slot'));
    await sent(t);
    await answer(
      t,
      h.db,
      h.stream,
      data: block([ms('slot', '2026-11-19T12:00:00', 'pending')]),
      settle: false,
    );
    await sent(t);
    expect(h.lastBody()['kind'], 'slot');
    h.prompts.confirmed = true;
    await t.tap(h.key('slot'));
    await sent(t);
    expect(h.prompts.asked['dateTime'], 1, reason: 'not asked again');
    expect(h.lastBody()['kind'], 'slot_confirm');
  });
}
