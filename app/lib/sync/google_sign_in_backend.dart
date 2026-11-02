/// One-tap Google sign-in, adapted from todo `lib/sync/`.
///
/// `crdt_sync` stays pure Dart (it also runs headless on the PC), so the
/// platform side lives in the `google_account_token` plugin (the system
/// account chooser, no browser, no Google client library) and the library
/// only ever receives a token string. The client id is the project's **Web**
/// OAuth client: Android must request a token minted for it, or Firebase
/// answers `audience mismatch`.
library;

import 'dart:developer';

import 'package:google_account_token/google_account_token.dart' as plugin;
import 'package:tutor/sync/google_platform.dart' as platform_gate;

/// Whether this build can sign in programmatically.
///
/// False on web (no AccountManager there) and when no client id is compiled
/// in: a button that can never succeed is worse than no button.
bool googleSignInSupported(String serverClientId) =>
    platform_gate.googleSignInSupported && serverClientId.isNotEmpty;

/// Returns a Google ID token for the account the user picks, or null.
///
/// Null rather than throwing when the user dismisses the picker: cancelling
/// is an ordinary outcome. [signInFn] exists for tests that bypass the
/// plugin entirely.
Future<String?> googleIdToken({
  required String serverClientId,
  Future<String?> Function()? signInFn,
}) async {
  if (signInFn != null) return await signInFn();
  if (serverClientId.isEmpty) {
    log('Google sign-in unavailable: no Web OAuth client id', level: 900);
    return null;
  }
  return await plugin.googleIdToken(serverClientId: serverClientId);
}
