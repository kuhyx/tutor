import 'package:flutter/material.dart';
import 'package:tutor/widgets/cue_chip.dart';

/// A plain snack bar with an error cue: [error] kept a change from being
/// saved (Home's subject pick).
void showNotSaved(BuildContext context, Object error) {
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      content: CueChip(kind: CueKind.error, semanticLabel: 'Not saved: $error'),
    ),
  );
}
