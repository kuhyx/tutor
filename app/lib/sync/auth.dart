/// The signed-in session: Google ID token -> Firebase refresh token in the
/// keystore -> short-lived ID tokens for every RTDB request (the shared
/// `rtdb_relay` package, with the tutor's own Google sign-in backend).
library;

import 'package:crdt_sync/crdt_sync.dart' show FirebaseCredentialStore;
import 'package:rtdb_relay/rtdb_relay.dart' as relay;
import 'package:tutor/config/firebase_config.dart';
import 'package:tutor/sync/google_sign_in_backend.dart';

export 'package:rtdb_relay/rtdb_relay.dart' show SignInOutcome;

/// Owns the Firebase session for this install.
class TutorAuth extends relay.RelayAuth {
  /// Creates the auth wrapper. Tests pass a memory `store` and fake `http`.
  new({
    required FirebaseConfig super.config,
    required super.store,
    super.httpClient,
    super.clock,
    super.adopt,
  }) : super(googleToken: googleIdToken);
}

/// The keystore-backed credential store (Android keystore; web storage).
FirebaseCredentialStore secureCredentialStore() =>
    relay.secureCredentialStore('tutor.firebase.credentials');
