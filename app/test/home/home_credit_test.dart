import 'package:flutter_test/flutter_test.dart';
import 'package:kuhy_credit/kuhy_credit.dart';
import 'package:tutor/ui/home_screen.dart';

import '../support/fake_stream.dart';
import '../support/ui.dart';

void main() {
  testWidgets('HomeScreen shows KuhyCredit in app bar leading', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      HomeScreen(services: s, onSignedOut: () {}),
    );
    expect(find.byType(KuhyCredit), findsOneWidget);
  });
}
