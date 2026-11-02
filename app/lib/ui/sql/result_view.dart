/// The outcome of a Run or a Check: match or not, the database's error, the
/// grid with its mismatches flagged, and (when the drill's expected rows
/// came along) a switch between what the SQL printed and what is expected.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/sql/sql_models.dart';
import 'package:tutor/ui/sql/data_grid.dart';

/// Shows one [SqlOutcome]; give it a new key per outcome so the switch
/// starts on "what the SQL printed".
class ResultView extends StatefulWidget {
  /// Creates the view.
  const new(this.outcome, {super.key});

  /// The outcome.
  final SqlOutcome outcome;

  @override
  State<ResultView> createState() => _ResultViewState();
}

class _ResultViewState extends State<ResultView> {
  bool _expected = false;

  @override
  Widget build(BuildContext context) {
    final o = widget.outcome;
    final scheme = Theme.of(context).colorScheme;
    if (!o.ok) {
      // A prediction of ERROR can be right: the verdict comes with the text.
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _verdict(o.match),
          const SizedBox(height: AppSpacing.sm),
          SelectableText(
            o.error ?? '',
            style: sqlMono.copyWith(color: scheme.error),
          ),
        ],
      );
    }
    final canSwitch = o.expectedRows.isNotEmpty;
    final show = _expected && canSwitch;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            _verdict(o.match),
            if (o.diff.isNotEmpty) ...[
              const SizedBox(width: AppSpacing.sm),
              Text('${o.diff.length}', style: sqlMono),
            ],
            const Spacer(),
            if (canSwitch)
              SegmentedButton<bool>(
                showSelectedIcon: false,
                segments: const [
                  ButtonSegment(
                    value: false,
                    icon: Icon(Icons.output, semanticLabel: 'Actual'),
                  ),
                  ButtonSegment(
                    value: true,
                    icon: Icon(Icons.flag_outlined, semanticLabel: 'Expected'),
                  ),
                ],
                selected: {_expected},
                onSelectionChanged: (s) => setState(() => _expected = s.first),
              ),
          ],
        ),
        const SizedBox(height: AppSpacing.sm),
        DataGridView(
          columns: show ? const [] : o.columns,
          rows: show ? o.expectedRows : o.rows,
          marked: o.marked(expected: show),
        ),
      ],
    );
  }
}

Widget _verdict(bool match) => Icon(
  match ? Icons.check_circle_outline : Icons.cancel_outlined,
  semanticLabel: match ? 'Match' : 'Mismatch',
  color: match ? AppPalette.success : AppPalette.danger,
);
