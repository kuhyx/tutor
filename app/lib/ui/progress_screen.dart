/// Progress (curriculum §7/§8): minutes per day against the daily target,
/// cards taught (cumulative), a day table, and every module's recall.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/home/remote_bits.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/progress/progress.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/fit_parts.dart';
import 'package:tutor/ui/layout.dart';
import 'package:tutor/ui/learn_bits.dart';
import 'package:tutor/ui/learn_rows.dart';
import 'package:tutor/ui/learn_tiles.dart';
import 'package:tutor/ui/progress_chart.dart';
import 'package:tutor/ui/progress_tiles.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// The Progress screen.
class ProgressScreen extends StatefulWidget {
  /// Creates the screen.
  const new({required this.services, super.key});

  /// Services.
  final TutorServices services;

  @override
  State<ProgressScreen> createState() => _ProgressScreenState();
}

class _ProgressScreenState extends State<ProgressScreen> {
  late final Future<(Stats?, List<ModuleProgress>)> _data = _load();

  Future<(Stats?, List<ModuleProgress>)> _load() async {
    final stats = await fetchStats(widget.services.client);
    final subjects = await widget.services.catalog.cached();
    return (stats, moduleProgress(subjects.values));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const SpokenLabel(
        semanticLabel: 'Progress',
        child: Icon(Icons.insights),
      ),
    ),
    body: FutureBuilder<(Stats?, List<ModuleProgress>)>(
      future: _data,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          return PageList(
            children: [
              CueChip(
                kind: CueKind.error,
                semanticLabel: 'Could not load: ${snap.error}',
              ),
            ],
          );
        }
        final (stats, modules) = snap.requireData;
        final days = timeline(stats?.days ?? const {});
        final first = <Widget>[
          if (days.isEmpty)
            const SizedBox(
              height: 240,
              child: GlyphEmpty(
                icon: Icons.insights,
                semanticLabel:
                    'No days yet. The PC writes a row per day once you learn.',
              ),
            )
          else ...[
            const LearnHeader(Icons.timer_outlined, 'Credited minutes per day'),
            ProgressChart(
              values: [for (final d in days) d.minutes],
              labels: [for (final d in days) d.day],
              cap: stats?.today.target,
              unit: 'min',
            ),
            const SizedBox(height: AppSpacing.lg),
            const LearnHeader(Icons.school_outlined, 'Cards taught (total)'),
            ProgressChart(
              values: [for (final d in days) d.taughtTotal],
              labels: [for (final d in days) d.day],
              line: true,
              unit: 'cards',
            ),
            const LearnHeader(Icons.calendar_month_outlined, 'Days'),
            _DayTable(days.reversed.toList()),
          ],
        ];
        final second = <Widget>[
          const LearnHeader(Icons.view_agenda_outlined, 'Modules'),
          // Its own height: a fixed box cut the padded 64 px glyph.
          if (modules.isEmpty)
            const GlyphEmpty(
              icon: Icons.assignment_outlined,
              semanticLabel: 'No approved plans yet.',
            ),
          for (final m in modules)
            ModuleRecallRow(m.module, subject: m.subject),
        ];
        return widthSwitch(
          // The phone page borrows the wide page's empty states and header.
          narrow: (_) => ProgressFit(
            stats: stats,
            modules: modules,
            header: second.first,
            noPlans: modules.isEmpty ? second[1] : null,
            empty: days.isEmpty ? first.single : null,
            allDays: _DayTable(days.reversed.toList()),
          ),
          wide: (_) => TwoColumnPage(
            firstFlex: 3,
            secondFlex: 2,
            first: first,
            second: second,
          ),
        );
      },
    ),
  );
}

class _DayTable extends StatelessWidget {
  const new(this.days);

  final List<DayPoint> days;

  static DataColumn _col(IconData icon, String label) => DataColumn(
    label: SpokenLabel(semanticLabel: label, child: Icon(icon)),
    numeric: true,
  );

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    scrollDirection: Axis.horizontal,
    child: DataTable(
      columns: [
        _col(Icons.calendar_month_outlined, 'Day'),
        _col(Icons.timer_outlined, 'Minutes'),
        _col(Icons.school_outlined, 'Taught'),
        _col(Icons.replay, 'Reviews'),
      ],
      rows: [
        for (final d in days)
          DataRow(
            cells: [
              DataCell(Text(d.day)),
              DataCell(Text('${d.minutes}')),
              DataCell(Text('${d.taught}')),
              DataCell(Text('${d.reviews}')),
            ],
          ),
      ],
    ),
  );
}
