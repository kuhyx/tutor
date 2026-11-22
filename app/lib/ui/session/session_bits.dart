/// Small parts of the Session's bottom panel.
library;

import 'dart:async';
import 'dart:math' as math;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/session/blocked_panel.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// Card done: Stop / Next; no check, the green answer box says it (2026-11-22).
class CardEnd extends StatelessWidget {
  /// Creates the bar; each [refused] Next shakes it, any tints it amber.
  const new({
    required this.onNext,
    required this.onStop,
    this.refused = 0,
    super.key,
  });

  /// Next card (stops this session, starts the next).
  final VoidCallback onNext;

  /// Stop here.
  final VoidCallback onStop;

  /// Next presses refused with nothing to do.
  final int refused;

  @override
  Widget build(BuildContext context) {
    final stop = GlyphButton(
      icon: Icons.stop_circle_outlined,
      semanticLabel: 'Stop here',
      onPressed: onStop,
    );
    // No autofocus: the follow-up composer below takes the keys.
    final next = Shake(
      trigger: refused,
      child: GlyphButton(
        icon: Icons.skip_next,
        semanticLabel: 'Next card',
        filled: true,
        tint: refused > 0 ? cueColor(context, CueKind.blocked) : null,
        onPressed: onNext,
      ),
    );
    return Wrap(
      alignment: WrapAlignment.end,
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: AppSpacing.sm,
      children: [stop, next],
    );
  }
}

/// Shakes [child] sideways once each time [trigger] changes.
class Shake extends StatefulWidget {
  /// Creates the shake.
  const new({required this.trigger, required this.child, super.key});

  /// A new value shakes.
  final int trigger;

  /// What shakes.
  final Widget child;

  @override
  State<Shake> createState() => _ShakeState();
}

class _ShakeState extends State<Shake> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 400),
  );

  @override
  void didUpdateWidget(Shake old) {
    super.didUpdateWidget(old);
    if (old.trigger != widget.trigger) _c.forward(from: 0);
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: _c,
    builder: (context, child) => Transform.translate(
      // Three swings that die out.
      offset: Offset(8 * (1 - _c.value) * math.sin(_c.value * 6 * math.pi), 0),
      child: child,
    ),
    child: widget.child,
  );
}

/// Start session (or continue the subject's open one).
class StartButton extends StatelessWidget {
  /// Creates the button.
  const new({required this.onStart, super.key});

  /// Starts.
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) => Align(
    alignment: Alignment.centerRight,
    child: GlyphButton(
      icon: Icons.play_arrow,
      semanticLabel: 'Start session',
      filled: true,
      onPressed: onStart,
    ),
  );
}

/// The request status, plus Continue once the session is over; a block
/// (locked, no card left) shows its one glyph instead ([BlockedPanel]).
class NotLiveStatus extends StatelessWidget {
  /// Creates the line.
  const new({
    required this.services,
    required this.runner,
    required this.view,
    required this.onRun,
    this.onGate,
    this.subject,
    super.key,
  });

  /// Reopens the module gate's review (the block's review glyph).
  final VoidCallback? onGate;

  /// Services (the catalog and Review, for the call to action).
  final TutorServices services;

  /// The screen's subject (a hint when a block names none).
  final String? subject;

  /// Runner.
  final RequestRunner runner;

  /// Session on screen.
  final SessionView? view;

  /// Runs a request (`session_resume`).
  final Future<RelayStatus> Function(RequestBody body) onRun;

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<RelayStatus?>(
    valueListenable: runner.status,
    builder: (context, s, _) => Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // A block is a call to action, shown once (not also as a status).
        if (s is RelayFailed && s.blocks)
          BlockedPanel(
            services: services,
            blocked: s.blocked!,
            kind: s.kind,
            text: s.text,
            subject: subject,
            onGate: onGate,
          )
        else
          RequestStatusLine(runner, stalledText: noReplyText),
        if (s is RelayFailed && s.code == 'not_live' && view != null)
          Align(
            alignment: Alignment.centerRight,
            child: GlyphButton(
              icon: Icons.play_arrow,
              semanticLabel: 'Continue this session',
              filled: true,
              onPressed: () => onRun(RequestBody.sessionResume(view!.sid)),
            ),
          ),
      ],
    ),
  );
}

/// The bottom panel's frame: on the phone the step bar stays pinned and
/// the composer scrolls itself; elsewhere the whole panel scrolls.
Widget sessionPanel(Widget child, {required bool phone, bool dense = false}) =>
    phone
    ? Padding(
        padding: EdgeInsets.all(dense ? AppSpacing.sm : AppSpacing.md),
        child: child,
      )
    : SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: child,
      );

/// A session with nothing to show yet: the first tutor turn (or the
/// request that finds the session) is on its way.
class Preparing extends StatelessWidget {
  /// Creates the wait.
  const new({super.key});

  @override
  Widget build(BuildContext context) => const Center(
    child: SpokenLabel(
      semanticLabel: 'The tutor is preparing this card...',
      liveRegion: true,
      child: CircularProgressIndicator(),
    ),
  );
}

/// The chat area while there is nothing to show: [waiting] = something is on
/// its way, else the empty state once [loaded], else a spinner.
class NoChat extends StatelessWidget {
  /// Creates the placeholder.
  const new({required this.waiting, required this.loaded, super.key});

  /// A request or a first tutor turn is on its way.
  final bool waiting;

  /// The feed has answered.
  final bool loaded;

  @override
  Widget build(BuildContext context) => waiting
      ? const Preparing()
      : loaded
      ? const Center(
          child: SpokenLabel(
            semanticLabel:
                'No session yet. Start one: the tutor first asks what you '
                'already know, then teaches what is missing.',
            child: Icon(Icons.chat_bubble_outline, size: 64),
          ),
        )
      : const Center(child: CircularProgressIndicator());
}
