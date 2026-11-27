import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/read_screen.dart';

import '../support/fake_stream.dart';
import '../support/ui.dart';

void main() {
  testWidgets('routes /read and /read/<subject> open read mode', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      Builder(
        builder: (context) => Column(
          children: [
            IconButton(
              key: const ValueKey('all'),
              icon: const Icon(Icons.add),
              onPressed: () => openRoute(context, s, '/read'),
            ),
            IconButton(
              key: const ValueKey('one'),
              icon: const Icon(Icons.remove),
              onPressed: () => openRoute(context, s, '/read/car'),
            ),
          ],
        ),
      ),
      settle: false,
    );
    await t.tap(find.byKey(const ValueKey('one')));
    await sent(t);
    expect(find.byType(ReadScreen), findsOne);
    expect(lastRequest(db).$2['body'], {'subject': 'car'});
    await answer(t, db, stream, data: {'empty': true});
    await t.pageBack();
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('all')));
    await sent(t);
    expect(lastRequest(db).$2['body'], {'subject': null});
  });
}
