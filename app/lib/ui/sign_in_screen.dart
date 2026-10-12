/// One-time Google sign-in with the sync account.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/sync/auth.dart';
import 'package:tutor/sync/google_sign_in_backend.dart';

/// Sign-in screen.
class SignInScreen extends StatefulWidget {
  /// Creates the screen.
  const new({
    required this.services,
    required this.onSignedIn,
    this.supported,
    this.tokenFetcher,
    super.key,
  });

  /// Services (for the auth).
  final TutorServices services;

  /// Called after a session is stored.
  final VoidCallback onSignedIn;

  /// Overrides the platform check (tests).
  final bool? supported;

  /// Overrides the Google picker (tests).
  final Future<String?> Function()? tokenFetcher;

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  bool _busy = false;
  String? _message;

  Future<void> _signIn() async {
    setState(() {
      _busy = true;
      _message = null;
    });
    String? message;
    try {
      final outcome = await widget.services.auth.signInWithGoogle(
        tokenFetcher: widget.tokenFetcher,
      );
      if (outcome == SignInOutcome.signedIn) {
        widget.onSignedIn();
        return;
      }
      message = 'Sign-in cancelled.';
    } on Object catch (error) {
      // `on Object`: the wrong-account guard throws FirebaseAuthError, the
      // plugin can throw Errors; both are shown, never swallowed.
      message = '$error';
    }
    if (mounted) {
      setState(() {
        _busy = false;
        _message = message;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final supported =
        widget.supported ??
        googleSignInSupported(widget.services.config.serverClientId);
    final text = Theme.of(context).textTheme;
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: kProseMaxWidth),
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('Tutor', style: text.headlineMedium),
                const SizedBox(height: AppSpacing.md),
                Text(
                  supported
                      ? 'Sign in once with the sync Google account.'
                      : 'Desktop sign-in comes with the desktop wrapper.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: AppSpacing.lg),
                if (supported)
                  FilledButton(
                    autofocus: true,
                    onPressed: _busy ? null : _signIn,
                    child: const Text('Sign in with Google'),
                  ),
                if (_message != null) ...[
                  const SizedBox(height: AppSpacing.md),
                  Text(_message!, textAlign: TextAlign.center),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
