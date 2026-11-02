/// The task side of a drill: the markdown (fenced SQL as code blocks), the
/// tables, the query to predict or the first expected rows.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/sql/sql_models.dart';
import 'package:tutor/ui/sql/data_grid.dart';
import 'package:tutor/ui/sql/rich_md.dart';

/// The widgets of the task panel for [drill].
List<Widget> taskWidgets(Drill drill) {
  const gap = SizedBox(height: AppSpacing.md);
  return [
    RichMd(drill.taskMd.replaceFirst(RegExp(r'^# .*\n+'), '')),
    if (drill.query.isNotEmpty) ...[gap, CodeBlock(drill.query)],
    ...tableWidgets(drill.tables),
    if (drill.preview.isNotEmpty) ...[
      gap,
      const Align(
        alignment: Alignment.centerLeft,
        child: Icon(Icons.flag_outlined, semanticLabel: 'Expected'),
      ),
      const SizedBox(height: AppSpacing.xs),
      DataGridView(columns: const [], rows: drill.preview),
    ],
  ];
}

/// Each table: its name over its grid, spaced.
List<Widget> tableWidgets(List<SqlTable> tables) => [
  for (final t in tables) ...[
    const SizedBox(height: AppSpacing.md),
    Text(t.name, style: sqlMono.copyWith(fontWeight: FontWeight.w700)),
    const SizedBox(height: AppSpacing.xs),
    DataGridView(columns: t.columns, rows: t.rows),
  ],
];
