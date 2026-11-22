/// Home's session button per [SessionKind]: its glyph and the one ledger
/// word its tooltip shows (textgate, kuhy 2026-11-22).
library;

import 'package:flutter/material.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/session/session_entry.dart';

/// The glyph and tooltip word of a session kind.
extension SessionKindGlyph on SessionKind {
  /// The button's glyph.
  IconData get glyph => switch (this) {
    SessionKind.learn => Icons.school_outlined,
    SessionKind.live => Icons.chat_bubble_outline,
    SessionKind.resume => Icons.play_circle_outline,
  };

  /// The tooltip's `tooltip_*` ledger word.
  String word(AppLocalizations l) => switch (this) {
    SessionKind.learn => l.tooltip_learn,
    SessionKind.live => l.tooltip_live,
    SessionKind.resume => l.tooltip_resume,
  };
}
