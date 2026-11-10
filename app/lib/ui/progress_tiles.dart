/// Progress on a phone: stat tiles, a 7-day chart, a tile per subject.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/progress/progress.dart';
import 'package:tutor/ui/fit_parts.dart';
import 'package:tutor/ui/learn_bits.dart';
import 'package:tutor/ui/learn_rows.dart';
import 'package:tutor/ui/learn_tiles.dart';
import 'package:tutor/ui/progress_chart.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/spoken_label.dart';

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
        : '${today.creditedMinutes}/${today.target}';
    final taught = days.isEmpty ? 0 : days.last.taughtTotal;
    return fitPage([
      _pad(
        _stats([
          (Icons.timer_outlined, 'Credited today', credited),
          (Icons.school_outlined, 'Cards taught', '$taught'),
        ]),
      ),
      const SizedBox(height: AppSpacing.sm),
      _pad(
        _stats([
          (Icons.calendar_month_outlined, 'Days logged', '${days.length}'),
          (
            Icons.verified_outlined,
            'Modules reviewed',
            '$reviewed/${widget.modules.length}',
          ),
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
                    _chip(Icons.timer_outlined, 'Minutes', taught: false),
                    _chip(Icons.school_outlined, 'Taught', taught: true),
                  ],
                ),
              ),
              GlyphButton(
                icon: Icons.table_rows_outlined,
                semanticLabel: 'All days',
                onPressed: () => showLearnSheet(
                  context,
                  header: const LearnHeader(
                    Icons.calendar_month_outlined,
                    'All days',
                  ),
                  children: (_) => [widget.allDays],
                ),
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
    return LearnTile(
      key: ValueKey('subject-stat-$i'),
      title: name,
      details: [
        RecallStat(recall),
        SpokenLabel(
          semanticLabel: '${rows.length} modules',
          child: GlyphStat(Icons.view_agenda_outlined, '${rows.length}'),
        ),
      ],
      onMore: () => showLearnSheet(
        context,
        header: ContentText(
          name,
          style: Theme.of(context).textTheme.titleLarge,
        ),
        children: (_) => [for (final m in rows) ModuleRecallRow(m.module)],
      ),
    );
  }

  Widget _chip(IconData icon, String label, {required bool taught}) =>
      GlyphChip(
        icon: icon,
        semanticLabel: label,
        selected: _taught == taught,
        onSelected: () => setState(() => _taught = taught),
      );

  // Glyph + number per stat; the old label is the spoken label.
  Widget _stats(List<(IconData, String, String)> cells) => Row(
    children: [
      for (final (i, (icon, label, value)) in cells.indexed) ...[
        if (i > 0) const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Card(
            margin: EdgeInsets.zero,
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.sm),
              child: SpokenLabel(
                semanticLabel: '$label: $value',
                child: GlyphStat(
                  icon,
                  value,
                  size: Theme.of(context).textTheme.titleLarge?.fontSize,
                ),
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
