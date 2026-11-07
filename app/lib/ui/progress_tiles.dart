/// Progress on a phone: stat tiles, a 7-day chart, a tile per subject.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/progress/progress.dart';
import 'package:tutor/progress/terms.dart';
import 'package:tutor/ui/card_state.dart';
import 'package:tutor/ui/fit_parts.dart';
import 'package:tutor/ui/progress_chart.dart';

/// The phone body of Progress; the wide page lends it its widgets.
class ProgressFit extends StatefulWidget {
  /// Creates the body.
  const new({
    required this.stats,
    required this.modules,
    required this.header,
    required this.allDays,
    this.empty,
    this.noPlans,
    super.key,
  });

  /// Today and the days.
  final Stats? stats;

  /// Every module, subjects in order.
  final List<ModuleProgress> modules;

  /// Above the subject tiles.
  final Widget header;

  /// The day table, for its sheet.
  final Widget allDays;

  /// Instead of the chart when no day is logged.
  final Widget? empty;

  /// Instead of the tiles when no plan is approved.
  final Widget? noPlans;

  @override
  State<ProgressFit> createState() => _ProgressFitState();
}

class _ProgressFitState extends State<ProgressFit> {
  bool _taught = false;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final days = timeline(widget.stats?.days ?? const {});
    final today = widget.stats?.today;
    final subjects = <String, List<ModuleProgress>>{};
    for (final m in widget.modules) {
      (subjects[m.subject] ??= []).add(m);
    }
    final reviewed = widget.modules
        .where((m) => m.module.status == ModuleStatus.mastered)
        .length;
    final week = days.length <= 7 ? days : days.sublist(days.length - 7);
    final names = subjects.keys.toList();
    final credited = today == null
        ? '-'
        : '${today.creditedMinutes}/${today.target} min';
    final taught = days.isEmpty ? 0 : days.last.taughtTotal;
    return fitPage([
      _pad(
        _stats([(l10n.creditedToday, credited), (l10n.cardsTaught, '$taught')]),
      ),
      const SizedBox(height: AppSpacing.sm),
      _pad(
        _stats([
          (l10n.daysLogged, '${days.length}'),
          (l10n.modulesReviewed, '$reviewed/${widget.modules.length}'),
        ]),
      ),
      ?widget.empty,
      if (widget.empty == null) ...[
        _pad(
          Row(
            children: [
              // A Wrap: at a large "Display size" the chips take two lines
              // instead of pushing the All days button off the screen.
              Expanded(
                child: Wrap(
                  spacing: AppSpacing.sm,
                  runSpacing: AppSpacing.xs,
                  children: [
                    _chip(l10n.minutes, taught: false),
                    _chip(l10n.taught, taught: true),
                  ],
                ),
              ),
              IconButton(
                tooltip: l10n.allDays,
                onPressed: () => showFitSheet(
                  context,
                  title: l10n.allDays,
                  children: (_) => [widget.allDays],
                ),
                icon: const Icon(Icons.table_rows_outlined),
              ),
            ],
          ),
        ),
        _pad(
          ProgressChart(
            values: [
              for (final d in week)
                if (_taught) d.taughtTotal else d.minutes,
            ],
            labels: [for (final d in week) d.day],
            cap: _taught ? null : today?.target,
            line: _taught,
            unit: _taught ? 'cards' : 'min',
          ),
        ),
      ],
      _pad(widget.header),
      if (widget.noPlans case final none?)
        _pad(none)
      else
        Expanded(
          child: FitTileGrid(
            itemCount: names.length,
            itemBuilder: (context, i) =>
                _subject(context, i, names[i], subjects[names[i]]!),
          ),
        ),
    ]);
  }

  Widget _subject(
    BuildContext context,
    int i,
    String name,
    List<ModuleProgress> rows,
  ) {
    final recall =
        rows.fold<double>(0, (sum, m) => sum + m.module.recall) / rows.length;
    return FitTile(
      key: ValueKey('subject-stat-$i'),
      title: name,
      lines: [
        'recall ${(recall * 100).round()}%',
        AppLocalizations.of(context).moduleCount(rows.length),
      ],
      onMore: () => showFitSheet(
        context,
        title: name,
        children: (_) => [for (final m in rows) _ModuleRow(m)],
      ),
    );
  }

  Widget _chip(String label, {required bool taught}) => ChoiceChip(
    label: Text(label),
    selected: _taught == taught,
    onSelected: (_) => setState(() => _taught = taught),
  );

  Widget _stats(List<(String, String)> cells) => Row(
    children: [
      for (final (i, (label, value)) in cells.indexed) ...[
        if (i > 0) const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Card(
            margin: EdgeInsets.zero,
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.sm),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(value, style: Theme.of(context).textTheme.titleLarge),
                  Text(label, maxLines: 1, overflow: TextOverflow.ellipsis),
                ],
              ),
            ),
          ),
        ),
      ],
    ],
  );
}

Widget _pad(Widget child) => Padding(
  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
  child: child,
);

class _ModuleRow extends StatelessWidget {
  const new(this.row);

  final ModuleProgress row;

  @override
  Widget build(BuildContext context) {
    final m = row.module;
    final badge = moduleBadge(m);
    return ListTile(
      title: Text(m.title),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: AppSpacing.xs),
        child: LinearProgressIndicator(value: m.recall),
      ),
      trailing: Explained(
        badgeHelp(badge),
        child: Text('${(m.recall * 100).round()}% · $badge'),
      ),
    );
  }
}
