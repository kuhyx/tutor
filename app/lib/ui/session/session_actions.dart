/// The Session AppBar's buttons: on a wide desktop window the card actions
/// and Known, then copy the session id; on narrow windows and the phone,
/// copy and the side panel drawer. Glyphs only (the old wording is spoken).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:tutor/ui/session/session_bar.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// The AppBar actions; [sid] is null until a session shows. [card] (the
/// wide desktop bar) puts the card actions and [mastered]'s Known glyph
/// first; without it, [wide] decides the drawer button.
List<Widget> sessionActions({
  required String? sid,
  required bool wide,
  CardActions? card,
  List<String> mastered = const [],
}) => [
  if (card != null) ...[...card.glyphs(), knownGlyph(mastered)],
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

/// The Session AppBar: [title] (the subject, content; a LeetCode unit with
/// its [lead] pencil) with [stats] beside it, or under it when [twoLines]
/// (a taller bar), then [actions]. [row] (the phone's LeetCode stats) is a
/// line under the whole bar: the bar there is too narrow for them beside
/// the title.
PreferredSizeWidget sessionAppBar({
  required String? title,
  required bool twoLines,
  required Widget? stats,
  required List<Widget> actions,
  IconData? lead,
  String? spoken,
  Widget? row,
}) => AppBar(
  toolbarHeight: twoLines && stats != null ? kBarTwoLineHeight : null,
  title: BarTitle(
    title: title,
    lead: lead,
    spoken: spoken,
    twoLines: twoLines,
    stats: stats,
  ),
  actions: actions,
  bottom: row == null
      ? null
      : PreferredSize(
          preferredSize: const Size.fromHeight(kBarRowHeight),
          child: Container(
            height: kBarRowHeight,
            alignment: AlignmentDirectional.centerStart,
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
            child: row,
          ),
        ),
);
