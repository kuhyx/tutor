/// The Session AppBar's buttons: copy the session id; on narrow windows,
/// open the side panel drawer. Glyphs only (the old wording is spoken).
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// The AppBar actions; [sid] is null until a session shows.
List<Widget> sessionActions({required String? sid, required bool wide}) => [
  if (sid != null)
    Builder(
      builder: (context) => GlyphButton(
        icon: Icons.copy_outlined,
        semanticLabel: 'Copy session id',
        onPressed: () => _copy(context, sid),
      ),
    ),
  if (!wide)
    Builder(
      builder: (context) => GlyphButton(
        icon: Icons.view_sidebar_outlined,
        semanticLabel: 'Card and progress',
        onPressed: Scaffold.of(context).openEndDrawer,
      ),
    ),
];

Future<void> _copy(BuildContext context, String sid) async {
  final messenger = ScaffoldMessenger.of(context);
  await Clipboard.setData(ClipboardData(text: sid));
  // Copied: a check glyph, never a sentence.
  messenger.showSnackBar(
    const SnackBar(
      content: CueChip(kind: CueKind.ok, semanticLabel: 'Session id copied'),
    ),
  );
}
