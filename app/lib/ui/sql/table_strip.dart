import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/sql/sql_models.dart';
import 'package:tutor/ui/fit_layouts.dart';
import 'package:tutor/ui/metrics_cap.dart';
import 'package:tutor/ui/sql/data_grid.dart';
import 'package:tutor/widgets/content_text.dart';

/// Tables side by side in a small font, at most [share] of the visible height.
class TableStrip extends StatelessWidget {
  /// Creates the strip.
  const new({required this.tables, this.share = 0.3, super.key});

  /// Tables to show.
  final List<SqlTable> tables;

  /// Largest part of the visible height.
  final double share;

  @override
  Widget build(BuildContext context) => CappedHeight(
    share: share,
    child: fitScroll(
      context,
      key: const ValueKey('table-strip'),
      child: SingleChildScrollView(
        key: const ValueKey('table-strip-x'),
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.xs,
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final t in tables)
              Padding(
                padding: const EdgeInsets.only(right: AppSpacing.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    ContentText(
                      t.name,
                      style: sqlMonoDense.copyWith(fontWeight: FontWeight.w700),
                    ),
                    DataGridView(columns: t.columns, rows: t.rows, dense: true),
                  ],
                ),
              ),
          ],
        ),
      ),
    ),
  );
}
