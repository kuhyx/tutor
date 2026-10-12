/// Root widget: not configured -> sign in -> Home.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/config/firebase_config.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/sign_in_screen.dart';

/// The app.
class TutorApp extends StatelessWidget {
  /// Creates the app; [open] builds the services once config is complete.
  const new({required this.config, required this.open, super.key});

  /// Build-time identifiers.
  final FirebaseConfig config;

  /// Opens the services.
  final Future<TutorServices> Function() open;

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Tutor',
    theme: buildLightTheme(),
    darkTheme: buildDarkTheme(),
    home: config.isComplete
        ? _Gate(open: open)
        : _Message(
            'This build has no Firebase identifiers '
            '(${config.missing.join(', ')}). Run '
            '`dart run tool/write_firebase_config.dart` in app/ and rebuild.',
          ),
  );
}

class _Gate extends StatefulWidget {
  const new({required this.open});

  final Future<TutorServices> Function() open;

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
              ? HomeScreen(services: services, onSignedOut: recheck)
              : SignInScreen(services: services, onSignedIn: recheck);
        },
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

  final String text;

  @override
  Widget build(BuildContext context) => Scaffold(
    body: Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: kProseMaxWidth),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Text(text, textAlign: TextAlign.center),
        ),
      ),
    ),
  );
}
