/// Tiles, headers, chips and sheets of the learning screens: names are
/// content, everything else is a glyph or a number.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/progress/terms.dart';
import 'package:tutor/ui/fit_parts.dart';
import 'package:tutor/ui/learn_bits.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// A 2-column grid cell of the phone pages: [title] is content (a name),
/// [details] are glyph + number rows. Tap = [onTap] (else [onMore]).
class LearnTile extends StatelessWidget {
  /// Creates the tile.
  const new({
    required this.title,
    required this.details,
    this.corner,
    this.onTap,
    this.onMore,
    this.marked = false,
    super.key,
  });

  /// The name (content).
  final String title;

  /// Glyph + number rows under the title.
  final List<Widget> details;

  /// Beside the title (a mark).
  final Widget? corner;

  /// The tile's action; defaults to [onMore].
  final VoidCallback? onTap;

  /// Opens the sheet.
  final VoidCallback? onMore;

  /// Needs attention: accent border.
  final bool marked;

  // FitTile's layout: FitTileGrid sizes its rows for exactly that tile.
  @override
  Widget build(BuildContext context) => FitTile(
    title: title,
    meta: details,
    corner: [?corner],
    onTap: onTap,
    onMore: onMore,
    marked: marked,
  );
}

/// A module's name as content, with its [ModuleMarkIcon].
class ModuleTitleRow extends StatelessWidget {
  /// Creates the row.
  const new(this.module, this.mark, {super.key});

  /// The module.
  final Module module;

  /// Its mark.
  final ModuleMark mark;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      ModuleMarkIcon(mark),
      const SizedBox(width: AppSpacing.sm),
      Expanded(child: ContentText(module.title)),
    ],
  );
}

/// A section's glyph in place of its heading; [semanticLabel] is the old
/// heading.
class LearnHeader extends StatelessWidget {
  /// Creates the header.
  const new(this.icon, this.semanticLabel, {super.key});

  /// The glyph.
  final IconData icon;

  /// The old heading, spoken only.
  final String semanticLabel;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
    child: Align(
      alignment: Alignment.centerLeft,
      child: SpokenLabel(
        semanticLabel: semanticLabel,
        child: Icon(
          icon,
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ),
    ),
  );
}

/// A choice chip that is only a glyph; exposes [selected].
class GlyphChip extends StatelessWidget {
  /// Creates the chip.
  const new({
    required this.icon,
    required this.semanticLabel,
    required this.selected,
    required this.onSelected,
    super.key,
  });

  /// The glyph.
  final IconData icon;

  /// The old chip word, spoken only.
  final String semanticLabel;

  /// Shown selected.
  final bool selected;

  /// Chosen.
  final VoidCallback onSelected;

  @override
  Widget build(BuildContext context) => Semantics(
    label: semanticLabel,
    button: true,
    selected: selected,
    onTap: onSelected,
    excludeSemantics: true,
    child: ChoiceChip(
      label: Icon(icon, size: AppTextSize.subtitle),
      selected: selected,
      onSelected: (_) => onSelected(),
    ),
  );
}

/// A bottom sheet opened by a tile: [header] (a name or a glyph), then the
/// [children]; sheets may scroll.
Future<void> showLearnSheet(
  BuildContext context, {
  required Widget header,
  required List<Widget> Function(BuildContext sheet) children,
}) => showModalBottomSheet<void>(
  context: context,
  isScrollControlled: true,
  useSafeArea: true,
  showDragHandle: true,
  builder: (sheet) => SingleChildScrollView(
    padding: const EdgeInsets.fromLTRB(
      AppSpacing.md,
      0,
      AppSpacing.md,
      AppSpacing.lg,
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        header,
        const SizedBox(height: AppSpacing.sm),
        ...children(sheet),
      ],
    ),
  ),
);
