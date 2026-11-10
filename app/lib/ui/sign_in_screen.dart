/// One-time Google sign-in with the sync account.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/sync/auth.dart';
import 'package:tutor/sync/google_sign_in_backend.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/spoken_label.dart';

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
    final failed = _message != null;
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (supported)
                SpokenLabel(
                  semanticLabel: 'Sign in with Google',
                  button: true,
                  enabled: !_busy,
                  onTap: _busy ? null : _signIn,
                  child: FilledButton(
                    autofocus: true,
                    onPressed: _busy ? null : _signIn,
                    style: FilledButton.styleFrom(
                      minimumSize: const Size.square(AppSpacing.xxl + 16),
                      shape: const CircleBorder(),
                    ),
                    // The Google "G" mark: one letter, not a word.
                    child: const Text(
                      'G',
                      style: TextStyle(
                        fontSize: AppTextSize.title,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                )
              else
                const CueChip(
                  kind: CueKind.offline,
                  icon: Icons.desktop_windows_outlined,
                  semanticLabel:
                      'Desktop: this window signs in from the tutor server '
                      'on the PC, once per server start. Restart the '
                      'tutor (it hands the session over again), then '
                      'reload this window.',
                ),
              if (failed) ...[
                const SizedBox(height: AppSpacing.md),
                // Cancelled or failed: red tint, shake, error glyph; the
                // detail is the spoken label.
                CueChip(
                  key: ValueKey(_message),
                  kind: CueKind.error,
                  semanticLabel: _message!,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
