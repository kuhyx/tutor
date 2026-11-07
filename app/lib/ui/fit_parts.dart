/// Phone fit layouts (build-mobile-app R7): pages that never scroll.
library;

import 'dart:math' as math;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/ui/layout.dart';

/// [narrow] on phones (below [kTwoColumns]), [wide] on the desktop.
Widget widthSwitch({
  required WidgetBuilder narrow,
  required WidgetBuilder wide,
}) => LayoutBuilder(
  builder: (context, box) =>
      box.maxWidth < kTwoColumns ? narrow(context) : wide(context),
);

/// A phone page inside the safe area; the last child usually `Expanded`.
Widget fitPage(List<Widget> children) => SafeArea(
  top: false,
  child: Padding(
    padding: const EdgeInsets.only(top: AppSpacing.sm),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: children,
    ),
  ),
);

/// A 2-column `FitGrid` of [FitTile]s whose rows are never shorter than a
/// tile with a two-line title and [lines] detail lines needs, at the
/// current text size. Rows stretch to share the height (up to a square), so
/// a short list fills the page instead of leaving an empty band.
class FitTileGrid extends StatelessWidget {
  /// Creates the grid.
  const new({
    required this.itemCount,
    required this.itemBuilder,
    this.lines = 2,
    super.key,
  });

  /// Number of tiles.
  final int itemCount;

  /// Builds tile `index`.
  final IndexedWidgetBuilder itemBuilder;

  /// Detail lines per tile, under the title.
  final int lines;

  static const _columns = 2;
  static const double _gap = AppSpacing.sm;
  static const double _side = AppSpacing.md;

  /// Height a [FitTile] with a two-line title and [lines] lines needs.
  static double tileHeight(BuildContext context, int lines) {
    final theme = Theme.of(context).textTheme;
    final scaler = MediaQuery.textScalerOf(context);
    double height(String text, TextStyle? style) {
      final painter = TextPainter(
        text: TextSpan(text: text, style: style),
        textScaler: scaler,
        textDirection: TextDirection.ltr,
      )..layout();
      final h = painter.height;
      painter.dispose();
      return h;
    }

    // Padding, the marked tile's 2 px border, and a pixel of rounding slack.
    return 2 * AppSpacing.sm +
        4 +
        1 +
        height('A\nA', theme.titleSmall) +
        lines * height('A', theme.bodySmall);
  }

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, box) {
      final cellW =
          (box.maxWidth - 2 * _side - _gap * (_columns - 1)) / _columns;
      final need = tileHeight(context, lines);
      final rows = math.max(1, (itemCount / _columns).ceil());
      // Shrunk a hair so FitGrid's floor() keeps every row on this page.
      final shared = box.maxHeight / rows - _gap - 0.01;
      final cellH = math.max(need, math.min(shared, cellW));
      return FitGrid(
        columns: _columns,
        minSquare: cellW > 0 ? cellH / cellW : 1,
        itemCount: itemCount,
        itemBuilder: itemBuilder,
        // A gap under the last row, so it never runs into the screen edge.
        padding: const EdgeInsets.fromLTRB(_side, 0, _side, _gap),
      );
    },
  );
}

/// A `FitGrid` cell: tap for its action, long-press for its sheet.
class FitTile extends StatelessWidget {
  /// Creates the tile.
  const new({
    required this.title,
    this.lines = const [],
    this.corner = const [],
    this.onTap,
    this.onMore,
    this.marked = false,
    super.key,
  });

  /// Up to two lines.
  final String title;

  /// One line each, clipped.
  final List<String> lines;

  /// Beside the title (status dot, due count).
  final List<Widget> corner;

  /// The tile's action; defaults to [onMore].
  final VoidCallback? onTap;

  /// Opens the sheet.
  final VoidCallback? onMore;

  /// Needs attention: accent border.
  final bool marked;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: EdgeInsets.zero,
      shape: marked
          ? RoundedRectangleBorder(
              side: BorderSide(color: theme.colorScheme.primary, width: 2),
              borderRadius: BorderRadius.circular(AppRadius.md),
            )
          : null,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap ?? onMore,
        onLongPress: onMore,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.sm),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.titleSmall,
                    ),
                  ),
                  ...corner,
                ],
              ),
              for (final line in lines)
                Flexible(
                  child: Text(
                    line,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodySmall,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// A bottom sheet titled [title]; sheets may scroll.
Future<void> showFitSheet(
  BuildContext context, {
  required String title,
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
        Text(title, style: Theme.of(sheet).textTheme.titleLarge),
        const SizedBox(height: AppSpacing.sm),
        ...children(sheet),
      ],
    ),
  ),
);
