/// An approved plan on a phone: header, Modules / Revisions chips, and a
/// tile per module whose sheet holds its full row and actions.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/progress/terms.dart';
import 'package:tutor/ui/fit_parts.dart';
import 'package:tutor/ui/module_tile.dart';

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
    final l10n = AppLocalizations.of(context);
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
              _chip(l10n.modules, revisions: false),
              const SizedBox(width: AppSpacing.sm),
              _chip(l10n.revisions, revisions: true),
            ],
          ),
        ),
      const SizedBox(height: AppSpacing.sm),
      Expanded(
        child: _revisions && history.isNotEmpty
            ? ListView(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                children: [
                  for (final h in history)
                    Text(l10n.revisionLine(h.rev, h.comment)),
                ],
              )
            : FitTileGrid(
                itemCount: widget.plan.modules.length,
                itemBuilder: (context, i) =>
                    _tile(context, i, widget.plan.modules[i]),
              ),
      ),
    ]);
  }

  Widget _chip(String label, {required bool revisions}) => ChoiceChip(
    label: Text(label),
    selected: _revisions == revisions,
    onSelected: (_) => setState(() => _revisions = revisions),
  );

  Widget _tile(BuildContext context, int i, Module m) {
    final review = widget.progress?.review[m.id];
    final failed = m.status == ModuleStatus.failed;
    final reviewable =
        review == ModuleReview.done && m.status != ModuleStatus.mastered;
    void sheet() => showFitSheet(
      context,
      title: m.title,
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
    return FitTile(
      key: ValueKey('module-tile-$i'),
      title: m.title,
      lines: [moduleBadge(m, review), 'recall ${(m.recall * 100).round()}%'],
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
