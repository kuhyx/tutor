// build-mobile-app R7: Sign in fits one Pixel 6a screen.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/sign_in_screen.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/fit.dart';
import '../support/label_finders.dart';
import '../support/services.dart';

void main() {
  for (final supported in [true, false]) {
    fitTest('Sign in, supported: $supported', (t, scale) async {
      pixelView(t, scale: scale);
      final s = services(FakeRtdb(), FakeStream());
      await pumpFit(
        t,
        SignInScreen(
          services: s,
          onSignedIn: () {},
          supported: supported,
          tokenFetcher: () async => null,
        ),
      );
      expectFits(t, state: 'start');
      if (!supported) return;
      await t.tap(controlByLabel('Sign in with Google'));
      await t.pumpAndSettle();
      expect(cueLabelled('Sign-in cancelled.'), findsOneWidget);
      expectFits(t, state: 'cancelled');
      expectReachable(t, controlByLabel('Sign in with Google'));
    });
  }
}
