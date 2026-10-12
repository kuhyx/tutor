/// The Firebase identifiers this build talks to.
///
/// The literal values live in the gitignored `firebase_local.dart`, written
/// by `tool/write_firebase_config.dart` (see app/README.md). This repo is
/// public, so the uid / API key never appear in source (DOCS-contract §10).
library;

import 'package:tutor/config/firebase_local.dart' as local;

/// The four identifiers the sync layer needs.
class FirebaseConfig {
  /// Creates a config; tests pass fakes.
  const new({
    required this.apiKey,
    required this.databaseUrl,
    required this.syncUid,
    required this.serverClientId,
  });

  /// The values compiled into this build.
  static const FirebaseConfig compiled = FirebaseConfig(
    apiKey: local.kFirebaseApiKey,
    databaseUrl: local.kFirebaseDatabaseUrl,
    syncUid: local.kFirebaseSyncUid,
    serverClientId: local.kGoogleServerClientId,
  );

  /// Web API key of the kuhy-syncs project.
  final String apiKey;

  /// Regional RTDB URL (`*.europe-west1.firebasedatabase.app`).
  final String databaseUrl;

  /// The uid the sync account must resolve to. A wrong Google account signs
  /// up a second user; this guard refuses it before anything is stored.
  final String syncUid;

  /// Google *Web* OAuth client id, used as the ID-token audience.
  final String serverClientId;

  /// Names of the identifiers that are empty in this build.
  List<String> get missing => [
    if (apiKey.isEmpty) 'apiKey',
    if (databaseUrl.isEmpty) 'databaseUrl',
    if (syncUid.isEmpty) 'syncUid',
  ];

  /// Whether the app can sign in and reach the database at all.
  bool get isComplete => missing.isEmpty;
}
