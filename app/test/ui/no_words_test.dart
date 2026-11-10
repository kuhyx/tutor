// textgate guard: every screen, at desktop and phone width, paints no app
// words (only icons, numbers, dates and content). Red on the text-heavy UI.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/sign_in_screen.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/fake_stream.dart';
import '../support/no_words.dart';
import '../support/ui.dart';

const _sizes = {'desktop': Size(1366, 900), 'phone': Size(412, 900)};

const _routes = [
  '/',
  '/plan/car',
  '/plan/garden',
  '/session',
  '/history',
  '/history/$fixtureLiveSid',
  '/history/20261011-090000-a1b2',
  '/progress',
  '/focus',
  '/sql',
  '/coach',
  '/mock',
  '/editor',
  '/editor/car',
  '/review',
  '/drill',
  '/report',
];

/// Lets a screen load without settling (spinners animate forever).
Future<void> _frames(WidgetTester t) async {
  for (var i = 0; i < 20; i++) {
    await t.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  for (final MapEntry(key: name, value: size) in _sizes.entries) {
    for (final route in _routes) {
      testWidgets('$route ($name) paints no words', (t) async {
        final s = await fixtureServices(fixtureDb(), FakeStream());
        await pumpScreen(
          t,
          HomeScreen(services: s, onSignedOut: () {}),
          size: size,
          settle: false,
        );
        await _frames(t);
        if (route != '/') {
          unawaited(openRoute(t.element(find.byType(HomeScreen)), s, route));
          await _frames(t);
        }
        expectNoWords(t, '$route ($name)');
      });
    }
    testWidgets('sign in ($name) paints no words', (t) async {
      final s = await fixtureServices(fixtureDb(), FakeStream());
      await pumpScreen(
        t,
        SignInScreen(services: s, onSignedIn: () {}),
        size: size,
      );
      expectNoWords(t, 'sign in ($name)');
    });
  }
}
