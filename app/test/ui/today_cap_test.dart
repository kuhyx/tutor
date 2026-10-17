// The Today card's "new cards x/y" reads stats `new_cap`, and says when
// today's limit was lifted ("Learn more anyway").
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/home_screen.dart';

import '../support/fake_stream.dart';
import '../support/ui.dart';

void main() {
  test('new_cap_lifted parses, and is written only when true', () {
    final j = {
      'day': '2026-10-17',
      'credited_minutes': 0,
      'target': 60,
      'new': 27,
      'new_cap': 25,
      'new_cap_lifted': true,
    };
    final t = Today.fromJson(j);
    expect(t.newCapLifted, isTrue);
    expect(t.toJson()['new_cap_lifted'], isTrue);
    final plain = Today.fromJson({...j}..remove('new_cap_lifted'));
    expect(plain.newCapLifted, isFalse);
    expect(plain.toJson().containsKey('new_cap_lifted'), isFalse);
  });

  testWidgets('Today: x/25 from stats, "(limit lifted)" once lifted', (
    t,
  ) async {
    final db = fixtureDb();
    db.root = setAt(db.root, 'tutor/v1/stats/today/new_cap', 25);
    final s = await fixtureServices(db, FakeStream());
    await pumpScreen(t, HomeScreen(services: s, onSignedOut: () {}));
    expect(find.textContaining('new cards 4/25'), findsOneWidget);
    expect(find.textContaining('limit lifted'), findsNothing);

    db.root = setAt(db.root, 'tutor/v1/stats/today/new', 27);
    db.root = setAt(db.root, 'tutor/v1/stats/today/new_cap_lifted', true);
    await t.tap(find.byTooltip('Refresh'));
    await t.pumpAndSettle();
    expect(
      find.textContaining('new cards 27/25 (limit lifted)'),
      findsOneWidget,
    );
  });
}
