/// The Home app bar's practice entries.
library;

import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/ui/nav.dart';

/// Focus and SQL buttons; [go] opens a screen and refreshes Home after.
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
];
