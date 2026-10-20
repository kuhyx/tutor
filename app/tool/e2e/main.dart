// Agent E2E build: the real app (real TutorServices, RtdbClient, SSE,
// request relay) pointed at a local Firebase RTDB emulator instead of the
// real database, with a throwaway session (an unsigned JWT: the emulator
// streams only for a parseable token; its rules are open) and an in-memory
// store. Never the compiled config, never the
// wrapper's /app/sync-credentials.
//
// `?db=http://127.0.0.1:<port>` (or `https://`: its h2 proxy) names the
// emulator (required; only a loopback URL is accepted). Semantics are always
// on, so a driver finds buttons by their label in the DOM
// (scripts/e2e_drive.py).
//
// Build: fvm flutter build web --release -t tool/e2e/main.dart \
//   -o build/web_e2e --base-href /app/   (scripts/e2e_sandbox.sh build)
import 'dart:convert';

import 'package:crdt_sync/crdt_sync.dart'
    show FirebaseCredentials, InMemoryCredentialStore;
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/config/firebase_config.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/ui/app.dart';
import 'package:tutor/ui/ui_zoom.dart';

const _loopback = {'127.0.0.1', 'localhost'};

/// The emulator URL from `?db=`, or empty (the app then shows "not
/// configured") when it is missing or not on this machine. `https` is the
/// sandbox's HTTP/2 proxy in front of it (scripts/e2e_h2proxy.go).
String emulatorUrl(Uri page) {
  final db = Uri.tryParse(page.queryParameters['db'] ?? '');
  final scheme = db?.scheme;
  if (db == null ||
      (scheme != 'http' && scheme != 'https') ||
      !_loopback.contains(db.host)) {
    return '';
  }
  return db.toString();
}

/// The token scripts/e2e_server.py uses too.
String emulatorToken() {
  String part(Map<String, Object> json) =>
      base64Url.encode(utf8.encode(jsonEncode(json))).replaceAll('=', '');
  const claims = {
    'sub': 'e2e',
    'user_id': 'e2e',
    'iat': 0,
    'exp': 4102444800,
    'aud': 'demo-tutor',
  };
  return '${part({'alg': 'none', 'typ': 'JWT'})}.${part(claims)}.';
}

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SemanticsBinding.instance.ensureSemantics();
  final config = FirebaseConfig(
    apiKey: 'e2e',
    databaseUrl: emulatorUrl(Uri.base),
    syncUid: 'e2e',
    serverClientId: '',
  );
  Future<TutorServices> open() async {
    final store = InMemoryCredentialStore();
    await store.save(
      FirebaseCredentials(
        idToken: emulatorToken(),
        refreshToken: 'e2e',
        expiresAt: DateTime.now().add(const Duration(days: 1)),
      ),
    );
    return await TutorServices.open(config, store: store, kv: MemoryKv());
  }

  runApp(
    TutorApp(
      config: config,
      open: open,
      initialRoute: Uri.base.queryParameters['screen'],
      zoom: UiZoom(),
    ),
  );
}
