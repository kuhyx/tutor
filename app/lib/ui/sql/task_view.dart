/// The task side of a drill: the markdown (fenced SQL as code blocks), the
/// tables, the query to predict or the first expected rows.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/sql/sql_models.dart';
import 'package:tutor/ui/session/md_text.dart';
import 'package:tutor/ui/sql/data_grid.dart';

final _fence = RegExp(r'```[a-zA-Z]*\n?(.*?)```', dotAll: true);

/// A selectable monospace block.
class CodeBlock extends StatelessWidget {
  /// Creates the block.
  const new(this.code, {super.key});

  /// The text.
  final String code;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      borderRadius: BorderRadius.circular(AppRadius.sm),
    ),
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.sm),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: SelectableText(code.trimRight(), style: sqlMono),
      ),
    ),
  );
}

/// The widgets of the task panel for [drill].
List<Widget> taskWidgets(Drill drill) {
  const gap = SizedBox(height: AppSpacing.md);
  final md = drill.taskMd;
  final parts = <Widget>[];
  var at = 0;
  for (final m in _fence.allMatches(md)) {
    final before = md.substring(at, m.start).trim();
    if (before.isNotEmpty) parts.add(MarkdownText(before));
    parts
      ..add(CodeBlock(m.group(1) ?? ''))
      ..add(const SizedBox(height: AppSpacing.sm));
    at = m.end;
  }
  final rest = md.substring(at).trim();
  if (rest.isNotEmpty) parts.add(MarkdownText(rest));
  return [
    ...parts,
    if (drill.query.isNotEmpty) ...[gap, CodeBlock(drill.query)],
    for (final t in drill.tables) ...[
      gap,
      Text(t.name, style: sqlMono.copyWith(fontWeight: FontWeight.w700)),
      const SizedBox(height: AppSpacing.xs),
      DataGridView(columns: t.columns, rows: t.rows),
    ],
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
