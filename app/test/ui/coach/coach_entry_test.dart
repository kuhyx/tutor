import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/coach/coach_picker.dart';
import 'package:tutor/ui/home_icons.dart';
import 'package:tutor/ui/nav.dart';

import '../../support/fake_rtdb.dart';
import '../../support/fake_stream.dart';
import '../../support/services.dart';
import '../../support/ui.dart';

void main() {
  late FakeRtdb db;
  late FakeStream stream;

  Future<void> pumpHost(WidgetTester t, WidgetBuilder body) async {
    db = FakeRtdb();
    stream = FakeStream();
    await pumpScreen(t, Scaffold(body: Builder(builder: body)), settle: false);
  }

  testWidgets('the Home coach icon opens the picker and asks for the list', (
    t,
  ) async {
    await pumpHost(
      t,
      (context) => Row(
        children: homeIcons(context, services(db, stream), (open) => open()),
      ),
    );
    await t.tap(find.byIcon(Icons.psychology_outlined));
    await t.pump();
    await t.pump(const Duration(milliseconds: 400));
    expect(find.byType(CoachPickerScreen), findsOneWidget);
    expect(lastRequest(db).$2['kind'], 'lc_list');
  });

  testWidgets('the /coach route opens the picker', (t) async {
    await pumpHost(
      t,
      (context) => TextButton(
        onPressed: () => openRoute(context, services(db, stream), '/coach'),
        child: const Text('go'),
      ),
    );
    await t.tap(find.text('go'));
    await t.pump();
    await t.pump(const Duration(milliseconds: 400));
    expect(find.byType(CoachPickerScreen), findsOneWidget);
  });
}
