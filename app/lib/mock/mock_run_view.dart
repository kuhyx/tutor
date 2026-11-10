import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/mock/mock_models.dart';
import 'package:tutor/ui/sql/data_grid.dart';
import 'package:tutor/widgets/content_text.dart';

/// The actual output of a Run: an error, a SQL grid or example verdicts.
class MockRunView extends StatelessWidget {
  /// Creates the view.
  const new(this.run, {super.key});

  /// What the Run printed.
  final MockRun run;

  @override
  Widget build(BuildContext context) {
    final error = run.error;
    if (error != null) {
      return ContentText(
        error,
        style: sqlMono.copyWith(color: Theme.of(context).colorScheme.error),
      );
    }
    if (run.examples.isNotEmpty) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [for (final e in run.examples) _Example(e)],
      );
    }
    return DataGridView(columns: run.columns, rows: run.rows);
  }
}

class _Example extends StatelessWidget {
  const new(this.e);

  final MockExample e;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: AppSpacing.sm),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          e.ok ? Icons.check_circle : Icons.cancel,
          key: ValueKey('example-${e.n}-${e.ok ? 'ok' : 'bad'}'),
          color: e.ok ? AppPalette.success : AppPalette.danger,
          size: 20,
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: ContentText(
            '${e.input}\n=> ${e.actual}'
            '${e.ok ? '' : '\n!= ${e.expected}'}'
            '${e.error == null ? '' : '\n${e.error}'}',
            style: sqlMono,
          ),
        ),
      ],
    ),
  );
}
