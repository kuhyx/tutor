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
import 'package:tutor/ui/progress_chart.dart';

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
    appBar: AppBar(title: const Text('Progress')),
    body: FutureBuilder<(Stats?, List<ModuleProgress>)>(
      future: _data,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          return PageList(children: [Text('Could not load: ${snap.error}')]);
        }
        final (stats, modules) = snap.requireData;
        final days = timeline(stats?.days ?? const {});
        final text = Theme.of(context).textTheme;
        return PageList(
          children: [
            if (days.isEmpty)
              const EmptyState(
                icon: Icons.insights,
                title: 'No days yet',
                message: 'The PC writes a row per day once you learn.',
              )
            else ...[
              Text('Credited minutes per day', style: text.titleMedium),
              ProgressChart(
                values: [for (final d in days) d.minutes],
                labels: [for (final d in days) d.day],
                cap: stats?.today.target,
                unit: 'min',
              ),
              const SizedBox(height: AppSpacing.lg),
              Text('Cards taught (total)', style: text.titleMedium),
              ProgressChart(
                values: [for (final d in days) d.taughtTotal],
                labels: [for (final d in days) d.day],
                line: true,
                unit: 'cards',
              ),
              const SectionHeader('Days'),
              _DayTable(days.reversed.toList()),
            ],
            const SectionHeader('Modules'),
            if (modules.isEmpty) const Text('No approved plans yet.'),
            for (final m in modules)
              ListTile(
                title: Text('${m.subject}: ${m.module.title}'),
                subtitle: Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.xs),
                  child: LinearProgressIndicator(value: m.module.recall),
                ),
                trailing: Text(
                  '${(m.module.recall * 100).round()}% · '
                  '${m.module.status.name}',
                ),
              ),
          ],
        );
      },
    ),
  );
}

class _DayTable extends StatelessWidget {
  const new(this.days);

  final List<DayPoint> days;

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    scrollDirection: Axis.horizontal,
    child: DataTable(
      columns: const [
        DataColumn(label: Text('Day')),
        DataColumn(label: Text('Minutes'), numeric: true),
        DataColumn(label: Text('Taught'), numeric: true),
        DataColumn(label: Text('Reviews'), numeric: true),
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
