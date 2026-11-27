/// Home's outage banner (mockup F1): while `stats.today.unavailable` is open,
/// a red-tinted row with the reason glyph, a ring for the time left until
/// the reset, and the free-chat glyph on the right. No words: the reason
/// and the reset time are the spoken label. It leaves by itself at the
/// window's end (Home only rebuilds on a reload).
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/model/outage_window.dart';
import 'package:tutor/ui/code_glyphs.dart';
import 'package:tutor/ui/relay_cue.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// The banner for [window]; nothing when it is null or already past.
class OutageBanner extends StatefulWidget {
  /// Creates the banner; [now] is the clock (tests).
  const new(this.window, {this.onFreeChat, this.now, super.key});

  /// Claude's limit window spans at most this long: a full ring.
  static const span = Duration(hours: 5);

  /// The outage as the worker last published it.
  final OutageWindow? window;

  /// Starts the free-model chat; null hides its glyph.
  final VoidCallback? onFreeChat;

  /// Clock; null = the wall clock.
  final DateTime Function()? now;

  @override
  State<OutageBanner> createState() => _OutageBannerState();
}

class _OutageBannerState extends State<OutageBanner> {
  Timer? _end;

  DateTime _now() => (widget.now ?? DateTime.now)();

  @override
  void initState() {
    super.initState();
    _arm();
  }

  @override
  void didUpdateWidget(OutageBanner old) {
    super.didUpdateWidget(old);
    if (old.window?.until != widget.window?.until) _arm();
  }

  // One timer at the window's end hides the banner.
  void _arm() {
    _end?.cancel();
    final w = widget.window;
    if (w == null || !w.openAt(_now())) return;
    final left = w.until * 1000 - _now().millisecondsSinceEpoch;
    _end = Timer(Duration(milliseconds: left), () {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _end?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final w = widget.window;
    if (w == null || !w.openAt(_now())) return const SizedBox.shrink();
    final said = Unavailable(until: w.until, reason: w.reason.wire).banner;
    final free = widget.onFreeChat;
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: AppPalette.danger.withValues(alpha: 0.14),
          border: Border.all(color: AppPalette.danger.withValues(alpha: 0.5)),
          borderRadius: BorderRadius.circular(AppRadius.md),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: AppSpacing.sm,
          ),
          child: Row(
            children: [
              SpokenLabel(
                semanticLabel: said,
                child: Icon(
                  unavailableIcon(w.reason),
                  color: AppPalette.danger,
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              DueRing(w.until * 1000, now: widget.now, span: OutageBanner.span),
              const Spacer(),
              if (free != null)
                GlyphButton(
                  icon: Icons.forum_outlined,
                  semanticLabel: 'Free chat',
                  tooltip: (l) => l.tooltip_ask,
                  tint: AppPalette.accent,
                  onPressed: free,
                ),
            ],
          ),
        ),
      ),
    );
  }
}
