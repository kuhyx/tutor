/// The Home app bar's practice entries.
library;

import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/nav.dart';

/// Focus, SQL and coach buttons; [go] opens a screen, then refreshes Home.
List<Widget> homeIcons(
  BuildContext context,
  TutorServices s,
  Future<void> Function(Future<void> Function() open) go,
) => [
  IconButton(
    tooltip: AppLocalizations.of(context).focus,
    onPressed: () => go(() => openFocus(context, s)),
    icon: const Icon(Icons.center_focus_strong_outlined),
  ),
  IconButton(
    onPressed: () => go(() => openSql(context, s)),
    icon: const Icon(Icons.storage_outlined, semanticLabel: 'SQL'),
  ),
  IconButton(
    onPressed: () => go(() => openCoach(context, s)),
    icon: const Icon(Icons.psychology_outlined, semanticLabel: 'Coach'),
  ),
];

/// The PC's heartbeat as a pill: checking, online, offline.
class PresenceChip extends StatelessWidget {
  /// Creates the pill.
  const new(this.state, {super.key});

  /// The watched presence.
  final ValueNotifier<PcPresence> state;

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<PcPresence>(
    valueListenable: state,
    builder: (context, value, _) {
      final (label, tip) = switch (value) {
        PcPresence.checking => ('PC: checking', 'Waiting for a heartbeat'),
        PcPresence.online => ('PC online', 'Replies come from the PC'),
        PcPresence.offline => ('PC offline', pcOfflineText),
      };
      return Tooltip(
        message: tip,
        child: Center(child: Pill(label, warn: value == PcPresence.offline)),
      );
    },
  );
}
