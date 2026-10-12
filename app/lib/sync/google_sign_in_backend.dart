/// One-tap Google sign-in, adapted from todo `lib/sync/`.
///
/// `crdt_sync` stays pure Dart (it also runs headless on the PC), so the
/// `google_sign_in` plugin lives here and the library only ever receives a
/// token string. The client id is the project's **Web** OAuth client: Android
/// must request a token minted for it, or Firebase answers `audience
/// mismatch`.
library;

import 'dart:developer';

import 'package:google_sign_in/google_sign_in.dart';
import 'package:tutor/sync/google_platform.dart' as platform_gate;

/// Whether this build can sign in programmatically.
///
/// False on web (Google Identity Services signs in only through its rendered
/// button; `authenticate()` throws there) and when no client id is compiled
/// in: a button that can never succeed is worse than no button.
bool googleSignInSupported(String serverClientId) =>
    platform_gate.googleSignInSupported && serverClientId.isNotEmpty;

/// Returns a Google ID token for the account the user picks, or null.
///
/// Null rather than throwing when the user dismisses the picker: cancelling
/// is an ordinary outcome. [signInFn] exists for tests, which cannot reach
/// the platform channel the plugin uses.
Future<String?> googleIdToken({
  required String serverClientId,
  Future<String?> Function()? signInFn,
}) async {
  if (signInFn != null) return await signInFn();
  if (serverClientId.isEmpty) {
    log('Google sign-in unavailable: no Web OAuth client id', level: 900);
    return null;
  }
  // The OS account picker is a platform channel `flutter test` has no
  // binding for; everything above is pure Dart and covered.
  // coverage:ignore-start
  try {
    await GoogleSignIn.instance.initialize(serverClientId: serverClientId);
    if (!GoogleSignIn.instance.supportsAuthenticate()) {
      log('Google sign-in is not available on this platform', level: 900);
      return null;
    }
    final account = await GoogleSignIn.instance.authenticate();
    return account.authentication.idToken;
  } on GoogleSignInException catch (error, stackTrace) {
    // Includes the user dismissing the picker, but a configuration failure
    // (unregistered SHA-1, wrong client id) arrives the same way: log it.
    log(
      'Google sign-in did not complete',
      level: 900,
      error: error,
      stackTrace: stackTrace,
    );
    return null;
  }
  // coverage:ignore-end
}
