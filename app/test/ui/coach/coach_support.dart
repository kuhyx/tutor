import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/coach/coach_requests.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/ui/coach/coach_screen.dart';

import '../../coach/coach_fixtures.dart';
import '../../support/fake_rtdb.dart';
import '../../support/fake_stream.dart';
import '../../support/services.dart';
import '../../support/ui.dart';

const phone = Size(411, 914);

/// Pixel 6a geometry (R7): px size, density, status and nav bars.
void pixel(WidgetTester t, {double keyboard = 0}) {
  t.view
    ..physicalSize = const Size(1080, 2400)
    ..devicePixelRatio = 2.625
    ..padding = const FakeViewPadding(top: 132, bottom: 63)
    ..viewInsets = FakeViewPadding(bottom: keyboard);
}

class CoachRig {
  new() : kv = MemoryKv();

  final MemoryKv kv;
  late FakeRtdb db;
  late FakeStream stream;

  Future<void> open(
    WidgetTester t, {
    Map<String, Object?>? first = openData,
    RequestBody? body,
    Size size = phone,
  }) async {
    db = FakeRtdb();
    stream = FakeStream();
    await pumpScreen(
      t,
      CoachScreen(
        key: UniqueKey(),
        services: services(db, stream, kv: kv),
        open: body ?? lcOpen(problem: 'two-sum'),
      ),
      settle: false,
      size: size,
    );
    await t.pump(const Duration(milliseconds: 50));
    expect(lastRequest(db).$2['kind'], 'lc_open');
    if (first != null) await reply(t, first);
  }

  Future<void> reply(
    WidgetTester t,
    Map<String, Object?> data, {
    String? code,
    Map<String, Object?> extra = const {},
  }) => answer(
    t,
    db,
    stream,
    data: data,
    code: code,
    extra: extra,
    settle: false,
  ).then((_) => t.pump(const Duration(milliseconds: 100)));

  Map<String, dynamic> body() =>
      lastRequest(db).$2['body'] as Map<String, dynamic>;

  String kind() => lastRequest(db).$2['kind'] as String;

  Future<void> type(WidgetTester t, String text) async {
    await t.enterText(find.byKey(const ValueKey('answer')), text);
    await t.pump();
  }

  Future<void> say(WidgetTester t, String text) async {
    await type(t, text);
    await tap(t, 'send');
  }

  Future<void> tap(WidgetTester t, String key) async {
    await t.tap(find.byKey(ValueKey(key)));
    await sent(t);
  }
}
