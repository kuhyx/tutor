import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/coach/coach_models.dart';
import 'package:tutor/ui/sql/data_grid.dart';

/// The outcome of a Run: passed/total, then per example what the code
/// printed against what the statement expects.
class CoachRunView extends StatelessWidget {
  /// Creates the view.
  const new(this.report, {super.key});

  /// The run.
  final RunReport report;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final r = report;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            _verdict(r.ok),
            const SizedBox(width: AppSpacing.sm),
            Text('${r.passed}/${r.total}', style: sqlMono),
          ],
        ),
        if (r.error != null)
          SelectableText(
            r.error!,
            style: sqlMono.copyWith(color: scheme.error),
          ),
        if (r.noExamples)
          const Icon(Icons.help_outline, semanticLabel: 'No examples'),
        for (final e in r.examples) _Example(e),
      ],
    );
  }
}

Widget _verdict(bool ok) => Icon(
  ok ? Icons.check_circle_outline : Icons.cancel_outlined,
  semanticLabel: ok ? 'Match' : 'Mismatch',
  color: ok ? AppPalette.success : AppPalette.danger,
);

class _Example extends StatelessWidget {
  const new(this.e);

  final ExampleRun e;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _verdict(e.ok),
              const SizedBox(width: AppSpacing.sm),
              Text('#${e.n}', style: sqlMono),
            ],
          ),
          if (e.error != null)
            SelectableText(
              e.error!,
              style: sqlMono.copyWith(color: scheme.error),
            ),
          if (e.rows.isNotEmpty || e.expectedRows.isNotEmpty) ...[
            const _Label(Icons.output, 'Actual'),
            DataGridView(
              columns: e.columns,
              rows: e.rows,
              marked: {for (final d in e.diff) (d.row, d.col)},
            ),
            const _Label(Icons.flag_outlined, 'Expected'),
            DataGridView(columns: const [], rows: e.expectedRows),
          ] else ...[
            if (e.got != null) _Line(Icons.output, 'Actual', e.got!),
            if (e.expected != null)
              _Line(Icons.flag_outlined, 'Expected', e.expected!),
          ],
        ],
      ),
    );
  }
}

class _Label extends StatelessWidget {
  const new(this.icon, this.label);

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: AppSpacing.xs),
    child: Icon(icon, semanticLabel: label, size: 18),
  );
}

class _Line extends StatelessWidget {
  const new(this.icon, this.label, this.text);

  final IconData icon;
  final String label;
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: AppSpacing.xs),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, semanticLabel: label, size: 18),
        const SizedBox(width: AppSpacing.sm),
        Expanded(child: SelectableText(text, style: sqlMono)),
      ],
    ),
  );
}
