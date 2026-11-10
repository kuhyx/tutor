/// The practice screens' fixed sentences as cues: a failure is a shaking
/// red chip, a system line (gate verdict, hold reason) an amber info chip.
/// The sentence is only the spoken label (textgate).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/widgets/cue_chip.dart';

/// A failure ([problem] is spoken only): red tint, shake, error glyph.
Widget problemCue(String problem, {Key? key}) => Padding(
  key: key,
  padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
  child: Align(
    alignment: AlignmentDirectional.centerStart,
    child: CueChip(kind: CueKind.error, semanticLabel: problem),
  ),
);

/// A system line ([note] is spoken only): amber chip, info glyph.
Widget noteCue(String note, {Key? key}) => Padding(
  key: key,
  padding: const EdgeInsets.symmetric(
    horizontal: AppSpacing.md,
    vertical: AppSpacing.xs,
  ),
  child: Align(
    alignment: AlignmentDirectional.centerStart,
    child: CueChip(
      kind: CueKind.blocked,
      icon: Icons.info_outline,
      semanticLabel: note,
    ),
  ),
);
