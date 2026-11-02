import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'coach_support.dart';

void main() {
  final rig = CoachRig();

  testWidgets('typing keeps the statement, capped, above the thread', (
    t,
  ) async {
    await rig.open(t);
    pixel(t, keyboard: 800);
    await t.tap(find.byKey(const ValueKey('answer')));
    await t.pump(const Duration(milliseconds: 100));
    final text = find.textContaining('Find two numbers');
    expect(text.hitTestable(), findsOneWidget);
    final body = find.ancestor(of: text, matching: find.byType(ConstrainedBox));
    const visible = (2400 - 800 - 132) / 2.625;
    expect(
      body.evaluate().any(
        (e) =>
            (e.renderObject! as RenderBox).size.height <= visible * 0.3 + 0.5,
      ),
      isTrue,
    );
  });
}
