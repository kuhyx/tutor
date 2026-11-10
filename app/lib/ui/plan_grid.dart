/// An approved plan on a phone: header, Modules / Revisions chips, and a
/// tile per module whose sheet holds its full row and actions.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/progress/terms.dart';
import 'package:tutor/ui/fit_parts.dart';
import 'package:tutor/ui/learn_bits.dart';
import 'package:tutor/ui/learn_rows.dart';
import 'package:tutor/ui/learn_tiles.dart';
import 'package:tutor/ui/module_tile.dart';
import 'package:tutor/widgets/content_text.dart';

/// The phone body of an approved plan.
class PlanFit extends StatefulWidget {
  /// Creates the body.
  const new({
    required this.header,
    required this.plan,
    required this.progress,
    required this.onRetry,
    required this.onReview,
    super.key,
  });

  /// Title, goal, status, request status.
  final List<Widget> header;

  /// The approved plan.
  final Plan plan;

  /// Folded progress, null until the log is folded.
  final SubjectProgress? progress;

  /// Generates failed modules again.
  final VoidCallback onRetry;

  /// Starts a module's review.
  final ValueChanged<Module> onReview;

  @override
  State<PlanFit> createState() => _PlanFitState();
}

class _PlanFitState extends State<PlanFit> {
  bool _revisions = false;

  @override
  Widget build(BuildContext context) {
    final history = widget.plan.history;
    return fitPage([
      _pad(
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: widget.header,
        ),
      ),
      if (history.isNotEmpty)
        _pad(
          Row(
            children: [
              _chip(Icons.view_agenda_outlined, 'Modules', revisions: false),
              const SizedBox(width: AppSpacing.sm),
              _chip(Icons.history, 'Revisions', revisions: true),
            ],
          ),
        ),
      const SizedBox(height: AppSpacing.sm),
      Expanded(
        child: _revisions && history.isNotEmpty
            ? ListView(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                children: [for (final h in history) RevisionLine(h)],
              )
            : FitTileGrid(
                itemCount: widget.plan.modules.length,
                itemBuilder: (context, i) =>
                    _tile(context, i, widget.plan.modules[i]),
              ),
      ),
    ]);
  }

  Widget _chip(IconData icon, String label, {required bool revisions}) =>
      GlyphChip(
        icon: icon,
        semanticLabel: label,
        selected: _revisions == revisions,
        onSelected: () => setState(() => _revisions = revisions),
      );

  Widget _tile(BuildContext context, int i, Module m) {
    final review = widget.progress?.review[m.id];
    final failed = m.status == ModuleStatus.failed;
    final reviewable =
        review == ModuleReview.done && m.status != ModuleStatus.mastered;
    void sheet() => showLearnSheet(
      context,
      header: ContentText(
        m.title,
        style: Theme.of(context).textTheme.titleLarge,
      ),
      children: (sheet) {
        void closeThen(VoidCallback run) {
          Navigator.of(sheet).pop();
          run();
        }

        return [
          ModuleProgressTile(
            module: m,
            tally: widget.progress?.modules[m.id],
            review: review,
            onRetry: () => closeThen(widget.onRetry),
            onReview: () => closeThen(() => widget.onReview(m)),
          ),
        ];
      },
    );
    final mark = moduleMark(m, review);
    return LearnTile(
      key: ValueKey('module-tile-$i'),
      title: m.title,
      corner: ModuleMarkIcon(mark),
      details: [RecallStat(m.recall)],
      marked: failed || reviewable,
      onMore: sheet,
    );
  }
}

/// [fit] on phones, [list] on the desktop.
Widget planLayout(Widget list, PlanFit Function() fit) =>
    widthSwitch(narrow: (_) => fit(), wide: (_) => list);

Widget _pad(Widget child) => Padding(
  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
  child: child,
);
