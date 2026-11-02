import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/mock/mock_models.dart';
import 'package:tutor/mock/mock_run_view.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/sql/sql_models.dart';
import 'package:tutor/ui/sql/data_grid.dart';
import 'package:tutor/ui/sql/rich_md.dart';

Grid _grid(Object? v) => [
  for (final r in (v as List<dynamic>? ?? const []))
    [for (final c in r as List<dynamic>) '${c ?? 'NULL'}'],
];

Set<(int, int)> _marked(Object? diff) => {
  for (final d in (diff as List<dynamic>? ?? const []))
    (((d as List<dynamic>)[0] as num).toInt(), (d[1] as num).toInt()),
};

/// What went wrong (or right) on one graded item, by section.
Widget mockItemDetail(MockItem item) {
  final d = item.detail;
  return switch (item.section) {
    MockSection.pyMcq => _Mcq(d),
    MockSection.pyCode => _Code(d),
    MockSection.sql => _Sql(d),
  };
}

class _Mcq extends StatelessWidget {
  const new(this.d);

  final Json d;

  @override
  Widget build(BuildContext context) {
    final good = intOr(d, 'correct_option');
    final chosen = intOr(d, 'chosen');
    final output = strOr(d, 'output');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final (i, o) in strings(d, 'options').indexed)
          ListTile(
            dense: true,
            key: ValueKey('option-$i'),
            leading: Icon(
              i == good
                  ? Icons.check_circle
                  : i == chosen
                  ? Icons.cancel
                  : Icons.circle_outlined,
              color: i == good
                  ? AppPalette.success
                  : i == chosen
                  ? AppPalette.danger
                  : null,
            ),
            title: Text(o, style: sqlMono),
          ),
        if (output != null) CodeBlock(output),
      ],
    );
  }
}

class _Code extends StatelessWidget {
  const new(this.d);

  final Json d;

  @override
  Widget build(BuildContext context) {
    final ratio = '${intOr(d, 'passed') ?? 0}/${intOr(d, 'total') ?? 0}';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(ratio, key: const ValueKey('ratio')),
        MockRunView((
          ok: true,
          error: null,
          columns: const [],
          rows: const [],
          examples: listOf(d, 'failed', parseExample),
        )),
      ],
    );
  }
}

class _Sql extends StatelessWidget {
  const new(this.d);

  final Json d;

  @override
  Widget build(BuildContext context) {
    final error = strOr(d, 'error');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (error != null) Text(error, style: sqlMono),
        if (error == null) ...[
          const Icon(Icons.person_outline, semanticLabel: 'Yours'),
          DataGridView(
            columns: strings(d, 'columns'),
            rows: _grid(d['rows']),
            marked: _marked(d['cell_diff']),
          ),
        ],
        const SizedBox(height: AppSpacing.sm),
        const Icon(Icons.flag_outlined, semanticLabel: 'Expected'),
        DataGridView(columns: const [], rows: _grid(d['expected_rows'])),
      ],
    );
  }
}
