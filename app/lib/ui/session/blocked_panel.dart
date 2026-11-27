/// A blocking result (`locked`, `no_card_left`) as ONE glyph, never a panel
/// of chips and buttons (kuhy, 2026-11-22: "a mess of icons"). The module
/// gate's review opens by itself (`throughGate`); what is left here:
///
/// - cards still to review (left early): the review glyph; tap reopens it;
/// - only cards read without Claude hold it: the "unchecked" glyph with
///   their count; tap asks again, which reopens their list;
/// - the next module's cards being written: an animated pencil;
/// - nothing to do now: a ring for when the next review falls due (or the
///   kind's glyph); tap opens Home on the subject.
///
/// Each glyph carries a one-word tooltip; the why is spoken only.
library;

import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/home/remote_bits.dart';
import 'package:tutor/relay/blocked.dart';
import 'package:tutor/ui/relay_cue.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// The glyph for [blocked].
class BlockedPanel extends StatelessWidget {
  /// Creates the glyph; [subject] is the screen's subject (a hint when the
  /// payload names none), [onGate] reopens the gate review.
  const new({
    required this.services,
    required this.blocked,
    required this.kind,
    required this.text,
    this.onGate,
    this.subject,
    this.now,
    super.key,
  });

  /// Services (the catalog and the Home pick).
  final TutorServices services;

  /// The block.
  final Blocked blocked;

  /// The result's kind: its glyph when there is no due time.
  final String? kind;

  /// Why, in one line (spoken only).
  final String text;

  /// Reopens the gate review (cards still to pass).
  final VoidCallback? onGate;

  /// The screen's subject.
  final String? subject;

  /// Clock (tests).
  final DateTime Function()? now;

  @override
  Widget build(BuildContext context) {
    final b = blocked;
    final Widget glyph;
    if (b.heldUnchecked) {
      glyph = GlyphButton(
        icon: Icons.pending_actions,
        semanticLabel:
            '${b.gateUnchecked.length} cards wait for Claude’s check',
        count: b.gateUnchecked.length,
        tooltip: (l) => l.tooltip_unchecked,
        filled: true,
        onPressed: onGate,
      );
    } else if (b.gated) {
      glyph = GlyphButton(
        icon: Icons.style,
        semanticLabel: text,
        tooltip: (l) => l.tooltip_review,
        filled: true,
        onPressed: onGate,
      );
    } else if (b.writing) {
      glyph = Tooltip(
        message: 'Writing',
        excludeFromSemantics: true, // the spoken line says it
        child: SpokenLabel(semanticLabel: text, child: const WritingPencil()),
      );
    } else {
      final due = b.dueAt;
      final at = (now ?? DateTime.now)().millisecondsSinceEpoch;
      glyph = Tooltip(
        message: 'Done',
        excludeFromSemantics: true, // the spoken line says it
        child: SpokenLabel(
          semanticLabel: text,
          onTap: () => unawaited(_home(context)),
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: () => unawaited(_home(context)),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: due != null && due > at
                  ? DueRing(due, now: now)
                  : Icon(
                      kindIcon(kind),
                      color: cueColor(context, CueKind.blocked),
                    ),
            ),
          ),
        ),
      );
    }
    return Align(alignment: AlignmentDirectional.centerStart, child: glyph);
  }

  // Home, on this subject (its progress row is the one picked).
  Future<void> _home(BuildContext context) async {
    final id = blocked.subjectId(
      await services.catalog.cached(),
      hint: subject,
    );
    if (id != null) {
      try {
        await setCurrentSubject(services.client, id);
      } on Exception catch (_) {
        // Offline: Home still opens, on the last pick.
      }
    }
    if (context.mounted) Navigator.of(context).popUntil((r) => r.isFirst);
  }
}

/// The next module's cards are being written: a pencil that writes.
class WritingPencil extends StatefulWidget {
  /// Creates the pencil.
  const new({super.key});

  @override
  State<WritingPencil> createState() => _WritingPencilState();
}

class _WritingPencilState extends State<WritingPencil>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Reduced motion: a still pencil.
    if (MediaQuery.disableAnimationsOf(context)) {
      _c.stop();
    } else if (!_c.isAnimating) {
      _c.repeat();
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: _c,
    builder: (context, child) {
      final t = _c.value * 2 * math.pi;
      return Transform.translate(
        offset: Offset(4 * math.sin(t), 2 * math.sin(2 * t)),
        child: child,
      );
    },
    child: Icon(Icons.edit, color: cueColor(context, CueKind.blocked)),
  );
}
