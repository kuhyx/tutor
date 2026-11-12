/// Root widget: not configured -> sign in -> e2e key -> Home.
library;

import 'package:crdt_sync_flutter/crdt_sync_flutter.dart'
    show E2ePassphraseButton;
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/config/firebase_config.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/ui/sign_in_screen.dart';
import 'package:tutor/ui/start_screen.dart';
import 'package:tutor/ui/ui_scale.dart';
import 'package:tutor/ui/ui_zoom.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/text_free_theme.dart';

/// The app.
class TutorApp extends StatelessWidget {
  /// Creates the app; [open] builds the services once config is complete.
  const new({
    required this.config,
    required this.open,
    this.initialRoute,
    this.zoom,
    super.key,
  });

  /// Build-time identifiers.
  final FirebaseConfig config;

  /// Opens the services.
  final Future<TutorServices> Function() open;

  /// Route opened over Home once signed in (`ui/nav.dart`).
  final String? initialRoute;

  /// The "Display size" zoom (`main` loads it from this install's store);
  /// null = 100%, unsaved.
  final UiZoom? zoom;

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Tutor', // the proper noun: window / tab title
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    theme: textFreeTheme(buildLightTheme()),
    darkTheme: textFreeTheme(buildDarkTheme()),
    builder: (context, child) => UiZoomHost(
      zoom: zoom,
      child: UiScale(child: child!),
    ),
    home: config.isComplete
        ? _Gate(open: open, initialRoute: initialRoute)
        : _Message(
            'This build has no Firebase identifiers '
            '(${config.missing.join(', ')}). Run '
            '`dart run tool/write_firebase_config.dart` in app/ and rebuild.',
          ),
  );
}

class _Gate extends StatefulWidget {
  const new({required this.open, this.initialRoute});

  final Future<TutorServices> Function() open;
  final String? initialRoute;

  @override
  State<_Gate> createState() => _GateState();
}

class _GateState extends State<_Gate> {
  late final Future<TutorServices> _services = widget.open();
  Future<bool>? _session;

  @override
  Widget build(BuildContext context) => FutureBuilder<TutorServices>(
    future: _services,
    builder: (context, snap) {
      final services = snap.data;
      if (snap.hasError) return _Message('Could not start: ${snap.error}');
      if (services == null) return const _Loading();
      return FutureBuilder<bool>(
        future: _session ??= services.auth.hasSession(),
        builder: (context, session) {
          if (!session.hasData) return const _Loading();
          void recheck() => setState(() {
            _session = services.auth.hasSession();
          });
          return session.data!
              ? E2eUnlock(
                  services: services,
                  child: StartScreen(
                    services: services,
                    onSignedOut: recheck,
                    initialRoute: widget.initialRoute,
                  ),
                )
              : SignInScreen(services: services, onSignedIn: recheck);
        },
      );
    },
  );
}

/// Shows [child] once the e2e key is open; until then only the lock button
/// (icon only, no text) and a retry: nothing syncs in plaintext meanwhile.
class E2eUnlock extends StatefulWidget {
  /// Creates the gate.
  const new({required this.services, required this.child, super.key});

  /// Whose key to open.
  final TutorServices services;

  /// Shown once unlocked.
  final Widget child;

  @override
  State<E2eUnlock> createState() => _E2eUnlockState();
}

class _E2eUnlockState extends State<E2eUnlock> {
  late Future<bool> _open = widget.services.e2e.unlock();

  void _retry() => setState(() {
    _open = widget.services.e2e.unlock();
  });

  @override
  Widget build(BuildContext context) => FutureBuilder<bool>(
    future: _open,
    builder: (context, snap) {
      if (snap.data ?? false) return widget.child;
      if (snap.connectionState != ConnectionState.done) {
        return const _Loading();
      }
      final why = snap.hasError ? '${snap.error}' : widget.services.e2e.reason;
      return Scaffold(
        body: Center(
          child: Semantics(
            label: 'Sync is locked ($why): enter the crdt-sync password',
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                E2ePassphraseButton(locked: true, onSaved: _retry),
                const SizedBox(width: AppSpacing.md),
                IconButton(icon: const Icon(Icons.refresh), onPressed: _retry),
              ],
            ),
          ),
        ),
      );
    },
  );
}

class _Loading extends StatelessWidget {
  const new();

  @override
  Widget build(BuildContext context) =>
      const Scaffold(body: Center(child: CircularProgressIndicator()));
}

class _Message extends StatelessWidget {
  const new(this.text);

  /// The spoken detail; the screen paints an error cue only.
  final String text;

  @override
  Widget build(BuildContext context) => Scaffold(
    body: Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: CueChip(kind: CueKind.error, semanticLabel: text),
      ),
    ),
  );
}
