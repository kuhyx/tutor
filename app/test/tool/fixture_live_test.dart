import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/plan_screen.dart';

import '../../tool/fixture/fixture_data.dart';
import '../../tool/fixture/fixture_live.dart';
import '../../tool/fixture/fixture_stream.dart';
import '../support/fake_rtdb.dart';
import '../support/services.dart';
import '../support/ui.dart';

void main() {
  test('bump delay: 20 s unless ?bump=<s>', () {
    expect(fixtureBumpDelay(const {}), const Duration(seconds: 20));
    expect(fixtureBumpDelay(const {'bump': '5'}), const Duration(seconds: 5));
    expect(fixtureBumpDelay(const {'bump': 'x'}), const Duration(seconds: 20));
  });

  testWidgets('screenshot build: Plan goes generating -> ready by itself', (
    t,
  ) async {
    final db = FakeRtdb()
      ..root = fixtureGenerating(
        setAt(null, 'tutor/v1', fixtureTree(fixtureNow)),
      );
    final stream = FixtureStream(
      db.client(),
      () => db.root,
      change: (
        after: fixtureBumpDelay(const {}),
        apply: () => db.root = fixtureCardsReady(db.root),
      ),
    );
    await pumpScreen(
      t,
      PlanScreen(services: services(db, stream), subject: 'car'),
      settle: false,
    );
    await t.pump(const Duration(seconds: 10));
    expect(find.textContaining('generating'), findsOneWidget);
    await t.pump(const Duration(seconds: 11));
    await t.pumpAndSettle();
    expect(find.textContaining('generating'), findsNothing);
    expect(find.textContaining('ready · 3 cards'), findsNWidgets(2));
    expect(getAt(db.root, 'tutor/v1/rev/catalog'), 8);
    expect(
      getAt(db.root, 'tutor/v1/subjects/car/cards/drv-gears/module'),
      'drivetrain',
    );
  });
}
