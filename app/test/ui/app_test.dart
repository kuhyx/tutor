import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/config/firebase_config.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/app.dart';
import 'package:tutor/ui/sign_in_screen.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/services.dart';

void main() {
  late FakeRtdb db;
  late FakeStream stream;

  setUp(() {
    db = FakeRtdb()
      ..root = setAt(null, 'tutor/v1/subjects/car/meta', {
        'title': 'How a car works',
        'status': 'draft',
        'created': 1,
        'rev': 1,
        'origin': 'generated',
      });
    db.root = setAt(db.root, 'tutor/v1/stats/today', {
      'day': '2026-10-12',
      'credited_minutes': 23,
      'target': 60,
      'new': 4,
      'new_cap': 10,
    });
    stream = FakeStream();
  });

  testWidgets('a build without identifiers says so', (tester) async {
    const empty = FirebaseConfig(
      apiKey: '',
      databaseUrl: '',
      syncUid: '',
      serverClientId: 'x',
    );
    await tester.pumpWidget(
      TutorApp(config: empty, open: () async => services(db, stream)),
    );
    expect(find.textContaining('write_firebase_config'), findsOneWidget);
  });

  testWidgets('open failure is shown', (tester) async {
    await tester.pumpWidget(
      TutorApp(config: testConfig, open: () async => throw StateError('boom')),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('boom'), findsOneWidget);
  });

  testWidgets('sign in -> Home with presence, due count and subjects', (
    tester,
  ) async {
    final s = services(db, stream);
    await tester.pumpWidget(TutorApp(config: testConfig, open: () async => s));
    await tester.pumpAndSettle();
    // Not Android in tests: the platform gate hides the button.
    expect(find.textContaining('Desktop sign-in'), findsOneWidget);
    await s.auth.signInWithGoogle(tokenFetcher: () async => 'g');
    await tester.pumpWidget(
      TutorApp(config: testConfig, open: () async => s, key: UniqueKey()),
    );
    await tester.pumpAndSettle();
    expect(find.text('How a car works'), findsOneWidget);
    expect(find.text('Review (0 due)'), findsOneWidget);
    expect(find.text('PC: checking'), findsOneWidget);
    stream.listens[Paths.workers]!
      ..add(const RtdbConnected())
      ..add(const RtdbPut('/', null));
    await tester.pumpAndSettle();
    expect(find.text('PC offline'), findsOneWidget);
    stream.listens[Paths.workers]!.add(const RtdbPut('/w', {'beat': 1}));
    await tester.pumpAndSettle();
    expect(find.text('PC online'), findsOneWidget);

    await tester.tap(find.byTooltip('Refresh'));
    await tester.pumpAndSettle();
    expect(find.text('How a car works'), findsOneWidget);

    await tester.tap(find.byTooltip('More'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Sign out'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Desktop sign-in'), findsOneWidget);
  });

  testWidgets('Home shows load errors and the offline banner', (tester) async {
    final s = services(db, stream);
    await s.auth.signInWithGoogle(tokenFetcher: () async => 'g');
    db.offline = true;
    await tester.pumpWidget(TutorApp(config: testConfig, open: () async => s));
    await tester.pumpAndSettle();
    expect(find.textContaining('Could not load'), findsOneWidget);
    db.offline = false;
    await tester.tap(find.byTooltip('Refresh'));
    await tester.pumpAndSettle();
    db.offline = true;
    await tester.tap(find.byTooltip('Refresh'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Offline'), findsOneWidget);
  });

  testWidgets('sign-in button: cancel, wrong account, success', (tester) async {
    var signedIn = 0;
    Future<void> pump(TutorServices s, Future<String?> Function() fetch) =>
        tester.pumpWidget(
          MaterialApp(
            home: SignInScreen(
              services: s,
              onSignedIn: () => signedIn++,
              supported: true,
              tokenFetcher: fetch,
            ),
          ),
        );
    await pump(services(db, stream), () async => null);
    await tester.tap(find.text('Sign in with Google'));
    await tester.pumpAndSettle();
    expect(find.text('Sign-in cancelled.'), findsOneWidget);

    await pump(services(db, stream, uid: 'other'), () async => 'g');
    await tester.tap(find.text('Sign in with Google'));
    await tester.pumpAndSettle();
    expect(find.textContaining('wrong account'), findsOneWidget);

    await pump(services(db, stream), () async => 'g');
    await tester.tap(find.text('Sign in with Google'));
    await tester.pumpAndSettle();
    expect(signedIn, 1);
  });
}
