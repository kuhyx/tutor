import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_account_token/google_account_token.dart'
    show kGoogleAccountTokenChannel;
import 'package:tutor/sync/google_sign_in_backend.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final messenger =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  MethodCall? seen;

  setUp(() => debugDefaultTargetPlatformOverride = TargetPlatform.android);

  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
    seen = null;
    messenger.setMockMethodCallHandler(kGoogleAccountTokenChannel, null);
  });

  void fakeChannel(Future<Object?> Function(MethodCall) handler) {
    messenger.setMockMethodCallHandler(kGoogleAccountTokenChannel, (call) {
      seen = call;
      return handler(call);
    });
  }

  test('asks the shared plugin for a token for the web client', () async {
    fakeChannel((_) async => 'jwt');
    expect(await googleIdToken(serverClientId: 'web-id'), 'jwt');
    expect(seen?.method, 'idToken');
    expect(seen?.arguments, {'serverClientId': 'web-id'});
  });

  test('a cancelled chooser is null, not an error', () async {
    fakeChannel((_) async => null);
    expect(await googleIdToken(serverClientId: 'web-id'), isNull);
  });

  test('depends on the shared plugin, not google_sign_in', () {
    final pubspec = File('pubspec.yaml').readAsStringSync();
    expect(pubspec, contains('google_account_token-v0.1.0'));
    expect(pubspec, isNot(contains('google_sign_in:')));
  });
}
