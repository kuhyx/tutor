/// The Home app bar's practice entries.
library;

import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/widgets/spoken_label.dart';
import 'package:tutor/widgets/text_free_theme.dart';

/// Focus, SQL and coach buttons; [go] opens a screen, then refreshes Home.
List<Widget> homeIcons(
  BuildContext context,
  TutorServices s,
  Future<void> Function(Future<void> Function() open) go,
) => [
  // "Focus" is a ledger-approved word: its tooltip stays.
  approvedTooltip(
    message: AppLocalizations.of(context).focus,
    child: IconButton(
      onPressed: () => go(() => openFocus(context, s)),
      icon: const Icon(Icons.center_focus_strong_outlined),
    ),
  ),
  GlyphButton(
    icon: Icons.storage_outlined,
    semanticLabel: 'SQL',
    onPressed: () => go(() => openSql(context, s)),
  ),
  GlyphButton(
    icon: Icons.psychology_outlined,
    semanticLabel: 'Coach',
    onPressed: () => go(() => openCoach(context, s)),
  ),
];

/// The PC's heartbeat as a glyph pill: checking, online, offline (warm).
class PresenceChip extends StatelessWidget {
  /// Creates the pill.
  const new(this.state, {super.key});

  /// The watched presence.
  final ValueNotifier<PcPresence> state;

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<PcPresence>(
    valueListenable: state,
    builder: (context, value, _) {
      final (icon, label) = switch (value) {
        PcPresence.checking => (Icons.sync, 'PC: checking'),
        PcPresence.online => (Icons.computer, 'PC online'),
        PcPresence.offline => (Icons.cloud_off, 'PC offline'),
      };
      return Center(
        child: GlyphPill(
          icon: icon,
          semanticLabel: label,
          warn: value == PcPresence.offline,
        ),
      );
    },
  );
}
