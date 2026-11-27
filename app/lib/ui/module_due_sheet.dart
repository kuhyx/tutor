/// A subject's due cards by module (part e79be0be-1): Home's red due badge
/// (phone) and the subject tile's review glyph (desktop) open this sheet.
/// One row per module with due cards, then the whole subject. The rows need
/// not sum to the subject's count: off-plan cards are in no module.
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/home/home_loader.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/nav_module_review.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/spoken_label.dart';
import 'package:tutor/widgets/text_free_theme.dart';

/// Home's sheet for [subject] (titled [title]) over [data]: a module row
/// runs that module's due cards ([openModuleReview]), the subject row all
/// of the subject's ([openReview]); [go] reloads Home on return.
void openDueSheet(
  BuildContext context,
  TutorServices s,
  HomeSnapshot data,
  String subject,
  String title, {
  required Future<void> Function(Future<void> Function() open) go,
}) => unawaited(
  showModuleDueSheet(
    context,
    data: data,
    subject: subject,
    onModule: (m) => go(() => openModuleReview(context, s, subject, m.module)),
    onSubject: () =>
        go(() => openReview(context, s, subject: subject, subjectTitle: title)),
  ),
);

/// The sheet of [subject] from [data]; a row closes it, then runs
/// [onModule] or [onSubject].
Future<void> showModuleDueSheet(
  BuildContext context, {
  required HomeSnapshot data,
  required String subject,
  required ValueChanged<ModuleRef> onModule,
  required VoidCallback onSubject,
}) {
  final entry = data.subjects.where((e) => e.id == subject).firstOrNull;
  final byModule = data.dueByModule[subject] ?? const <String, int>{};
  final modules = [
    for (final m in entry?.data?.plan?.modules ?? const <Module>[])
      if ((byModule[m.id] ?? 0) > 0) ModuleRef.of(subject, m),
  ];
  final total = data.dueBySubject[subject] ?? 0;
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (sheet) {
      VoidCallback close(VoidCallback run) => () {
        Navigator.of(sheet).pop();
        run();
      };
      return SingleChildScrollView(
        padding: const EdgeInsets.only(bottom: AppSpacing.lg),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final m in modules)
              DueRow(
                semanticLabel: 'Review ${m.title} (${byModule[m.module]} due)',
                count: byModule[m.module]!,
                onTap: close(() => onModule(m)),
                child: ContentText(m.title),
              ),
            DueRow(
              semanticLabel: 'Review all ($total due)',
              count: total,
              word: (l) => l.tooltip_all,
              onTap: close(onSubject),
              child: const Align(
                alignment: Alignment.centerLeft,
                child: Icon(Icons.all_inclusive, color: AppPalette.accent),
              ),
            ),
          ],
        ),
      );
    },
  );
}

/// One row of the sheet: [child] (a module name or a glyph), then its red
/// due [count]; the whole row is the button.
class DueRow extends StatelessWidget {
  /// Creates the row.
  const new({
    required this.semanticLabel,
    required this.count,
    required this.onTap,
    required this.child,
    this.word,
    super.key,
  });

  /// What a screen reader says.
  final String semanticLabel;

  /// Due cards.
  final int count;

  /// Runs the review.
  final VoidCallback onTap;

  /// The name or glyph.
  final Widget child;

  /// One hover word naming a glyph [child]; null = none.
  final String Function(AppLocalizations l)? word;

  @override
  Widget build(BuildContext context) {
    final row = SpokenLabel(
      semanticLabel: semanticLabel,
      button: true,
      onTap: onTap,
      child: ListTile(
        title: child,
        trailing: CountBadge(count, color: AppPalette.danger),
        onTap: onTap,
      ),
    );
    final l10n = Localizations.of<AppLocalizations>(context, AppLocalizations);
    final w = word;
    if (w == null || l10n == null) return row;
    return approvedTooltip(
      message: w(l10n),
      excludeFromSemantics: true,
      child: row,
    );
  }
}

/// A phone subject tile's red due badge; with [onTap] it is the button
/// that opens the sheet.
class DueBadge extends StatelessWidget {
  /// Creates the badge.
  const new(this.count, {this.onTap, super.key});

  /// The subject's due cards.
  final int count;

  /// Opens the sheet; null = a plain badge.
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final badge = Badge(label: Text('$count'));
    final tap = onTap;
    if (tap == null) return badge;
    return SpokenLabel(
      semanticLabel: 'Review by module ($count due)',
      button: true,
      onTap: tap,
      child: InkResponse(
        onTap: tap,
        radius: AppSpacing.md,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xs),
          child: badge,
        ),
      ),
    );
  }
}
