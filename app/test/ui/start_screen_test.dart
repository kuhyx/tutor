import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/app.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/today_screen.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/services.dart';
import '../support/ui.dart';

const Map<String, Object?> _plan = {
  'date': '2026-11-03',
  'steps': [
    {
      'id': 's1',
      'title': 'Coach: palindromic subsequence',
      'what': 'Finish it.',
      'kind': 'coach',
      'target': 'longest-palindromic-subsequence',
      'done': false,
    },
  ],
  'current': 's1',
};

void main() {
  late FakeRtdb db;
  late FakeStream stream;

  Future<void> launch(WidgetTester t, Map<String, Object?> data) async {
    db = FakeRtdb();
    stream = FakeStream();
    final s = services(db, stream);
    addTearDown(s.focus.dispose);
    await s.auth.signInWithGoogle(tokenFetcher: () async => 'g');
    await t.pumpWidget(TutorApp(config: testConfig, open: () async => s));
    await sent(t);
    await sent(t);
    expect(lastRequest(db).$2['kind'], 'plan_today');
    await answer(t, db, stream, data: data, settle: false);
    await sent(t);
  }

  testWidgets('a plan for today opens Today, not Home', (t) async {
    await launch(t, _plan);
    expect(find.byType(TodayScreen), findsOneWidget);
    expect(find.text('Coach: palindromic subsequence'), findsOneWidget);
    expect(find.byType(HomeScreen), findsNothing);
  });

  testWidgets('no plan opens Home', (t) async {
    await launch(t, {'date': '2026-11-03'});
    expect(find.byType(HomeScreen), findsOneWidget);
    expect(find.byType(TodayScreen), findsNothing);
  });
}
