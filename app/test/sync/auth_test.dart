import 'dart:convert';

import 'package:crdt_sync/crdt_sync.dart'
    show FirebaseAuthError, FirebaseCredentials, InMemoryCredentialStore;
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tutor/config/firebase_config.dart';
import 'package:tutor/sync/auth.dart';
import 'package:tutor/sync/google_sign_in_backend.dart';

const _config = FirebaseConfig(
  apiKey: 'key',
  databaseUrl: 'https://db',
  syncUid: 'right-uid',
  serverClientId: '',
);

MockClient _idp(String uid) => MockClient(
  (_) async => http.Response(
    jsonEncode({
      'localId': uid,
      'idToken': 'id-1',
      'refreshToken': 'refresh-1',
      'expiresIn': '3600',
    }),
    200,
  ),
);

class _BrokenStore extends InMemoryCredentialStore {
  @override
  Future<FirebaseCredentials?> load() => throw ArgumentError('Uri.base');
}

void main() {
  test('right account: session stored, token served', () async {
    final store = InMemoryCredentialStore();
    final auth = TutorAuth(
      config: _config,
      store: store,
      httpClient: _idp('right-uid'),
    );
    expect(await auth.hasSession(), isFalse);
    final out = await auth.signInWithGoogle(tokenFetcher: () async => 'g');
    expect(out, SignInOutcome.signedIn);
    expect(await auth.hasSession(), isTrue);
    expect(await auth.idToken(), 'id-1');
    await auth.signOut();
    expect(await store.load(), isNull);
  });

  test('wrong account throws and stores nothing', () async {
    final store = InMemoryCredentialStore();
    final auth = TutorAuth(
      config: _config,
      store: store,
      httpClient: _idp('second-user'),
    );
    await expectLater(
      auth.signInWithGoogle(tokenFetcher: () async => 'g'),
      throwsA(isA<FirebaseAuthError>()),
    );
    expect(await store.load(), isNull);
  });

  test('cancelled picker and missing client id are not errors', () async {
    final auth = TutorAuth(config: _config, store: InMemoryCredentialStore());
    expect(
      await auth.signInWithGoogle(tokenFetcher: () async => null),
      SignInOutcome.cancelled,
    );
    // No client id compiled in: the default fetcher declines.
    expect(await auth.signInWithGoogle(), SignInOutcome.cancelled);
  });

  test('a store that throws an Error reads as signed out', () async {
    final auth = TutorAuth(config: _config, store: _BrokenStore());
    expect(await auth.hasSession(), isFalse);
  });

  test('google sign-in gate and token passthrough', () async {
    expect(googleSignInSupported(''), isFalse);
    expect(googleSignInSupported('client'), isFalse); // not Android
    expect(
      await googleIdToken(serverClientId: 'c', signInFn: () async => 'tok'),
      'tok',
    );
    expect(await googleIdToken(serverClientId: ''), isNull);
  });
}
