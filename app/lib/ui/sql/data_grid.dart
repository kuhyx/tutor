/// A read-only monospace table; marked cells get a fill and a thick border.
library;

import 'dart:math';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/sql/sql_models.dart';
import 'package:tutor/widgets/content_text.dart';

/// Monospace text at table size.
const TextStyle sqlMono = TextStyle(
  fontFamily: 'monospace',
  fontSize: AppTextSize.label,
);

/// The same at strip size.
const TextStyle sqlMonoDense = TextStyle(fontFamily: 'monospace', fontSize: 11);

/// Header [columns], body [rows], and the (row, col) cells to flag.
class DataGridView extends StatelessWidget {
  /// Creates the grid.
  const new({
    required this.columns,
    required this.rows,
    this.marked = const {},
    this.dense = false,
    super.key,
  });

  /// Header cells.
  final List<String> columns;

  /// Body rows.
  final Grid rows;

  /// Flagged body cells, 0-based.
  final Set<(int, int)> marked;

  /// Smaller font and padding, for a strip.
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final width = rows.fold(columns.length, (n, r) => max(n, r.length));
    if (width == 0) return const SizedBox.shrink();
    Widget cell(String text, {bool head = false, Key? key, bool hit = false}) =>
        Container(
          key: key,
          padding: EdgeInsets.symmetric(
            horizontal: dense ? AppSpacing.xs : AppSpacing.sm,
            vertical: dense ? 1 : AppSpacing.xs,
          ),
          decoration: BoxDecoration(
            color: hit
                ? AppPalette.danger.withValues(alpha: 0.28)
                : head
                ? scheme.surfaceContainerHighest
                : null,
            border: hit ? Border.all(color: AppPalette.danger, width: 2) : null,
          ),
          child: ContentText(
            text,
            style: (dense ? sqlMonoDense : sqlMono).copyWith(
              fontWeight: head || hit ? FontWeight.w700 : null,
            ),
          ),
        );
    List<Widget> pad(List<Widget> cells) => [
      ...cells,
      for (var i = cells.length; i < width; i++) const SizedBox.shrink(),
    ];
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Table(
        defaultColumnWidth: const IntrinsicColumnWidth(),
        border: TableBorder.all(color: scheme.outlineVariant),
        children: [
          if (columns.isNotEmpty)
            TableRow(
              children: pad([for (final c in columns) cell(c, head: true)]),
            ),
          for (final (r, row) in rows.indexed)
            TableRow(
              children: pad([
                for (final (c, text) in row.indexed)
                  cell(
                    text,
                    hit: marked.contains((r, c)),
                    key: marked.contains((r, c))
                        ? ValueKey('mark-$r-$c')
                        : null,
                  ),
              ]),
            ),
        ],
      ),
    );
  }
}
