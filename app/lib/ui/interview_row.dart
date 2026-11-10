/// The row of milestone icons and the error state under it. Icons only: grey
/// pending, green done, red missed or unknown, with a badge so colour is
/// never the only cue (textgate).
library;

import 'dart:math';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/focus/interview_models.dart';
import 'package:tutor/ui/interview_labels.dart';
import 'package:tutor/ui/relay_cue.dart';

/// The six icons, left to right.
enum Slot {
  /// Rules screenshot.
  rules('rules', Icons.visibility),

  /// Trip question.
  trip('trip', Icons.luggage),

  /// Phone prep.
  phone('phone', Icons.smartphone),

  /// Today's budget (not a server milestone).
  clock('clock', Icons.schedule),

  /// Timed mock.
  mock('mock', Icons.videocam),

  /// Test slot.
  slot('slot', Icons.event);

  new(this.name, this.icon);

  /// Key suffix and label stem.
  final String name;

  /// The glyph.
  final IconData icon;
}

/// Colour of [light].
Color lightColor(BuildContext context, Light light) => switch (light) {
  Light.green => AppPalette.success,
  Light.red => AppPalette.danger,
  Light.grey => Theme.of(context).disabledColor,
};

/// One tappable milestone icon.
class MilestoneIcon extends StatelessWidget {
  /// Creates the icon for [slot] lit as [light]; a null [onTap] is inert.
  const new(this.slot, this.light, {this.onTap, super.key});

  /// Which icon.
  final Slot slot;

  /// Its state.
  final Light light;

  /// Opens the evidence action.
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final color = lightColor(context, light);
    final badge = switch (light) {
      Light.green => Icons.check_circle,
      Light.red => Icons.error_outline,
      Light.grey => null,
    };
    return Semantics(
      label: a11y('interview-ms-${slot.name}'),
      button: onTap != null,
      excludeSemantics: true,
      child: InkResponse(
        key: ValueKey('ms:${slot.name}'),
        onTap: onTap,
        radius: 28,
        child: SizedBox.square(
          dimension: 48,
          child: Stack(
            alignment: Alignment.center,
            children: [
              Icon(slot.icon, size: 30, color: color),
              if (badge != null)
                Positioned(
                  right: 4,
                  bottom: 4,
                  child: Icon(badge, size: 15, color: color),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The refusal / failure state: the failed result's kind as its own glyph
/// (DOCS-relay-kinds.md), tinted calm for a block and red for an error, and
/// shaking once; the app's own sentence is only its semantics label, never
/// the worker's words.
class InterviewError extends StatelessWidget {
  /// Creates the state for [text], drawn by [kind].
  const new(this.text, {this.kind, super.key});

  /// The app's own sentence for the case (spoken only).
  final String text;

  /// The failed result's kind; null or unknown = the generic error glyph.
  final String? kind;

  @override
  Widget build(BuildContext context) {
    final color = kindIsCalm(kind) ? AppPalette.warning : AppPalette.danger;
    return Semantics(
      label: text,
      excludeSemantics: true,
      child: TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: 1),
        duration: const Duration(milliseconds: 420),
        builder: (context, t, child) => Transform.translate(
          offset: Offset(8 * (1 - t) * sin(t * 10 * pi), 0), // dies out
          child: child,
        ),
        child: Container(
          alignment: Alignment.center,
          height: 40,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.14),
            borderRadius: BorderRadius.circular(AppSpacing.sm),
          ),
          child: Icon(kindIcon(kind), color: color),
        ),
      ),
    );
  }
}
