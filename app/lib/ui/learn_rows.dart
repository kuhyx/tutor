/// Rows of the learning screens: a module's recall, a plan revision, a
/// subject's status glyph.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/progress/terms.dart';
import 'package:tutor/ui/card_state.dart';
import 'package:tutor/ui/learn_bits.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// A module of Progress: its name as content (with the [subject] before
/// it), a recall bar, and recall % + mark.
class ModuleRecallRow extends StatelessWidget {
  /// Creates the row.
  const new(this.module, {this.subject, super.key});

  /// The module.
  final Module module;

  /// Its subject's title, when several subjects share the page.
  final String? subject;

  @override
  Widget build(BuildContext context) => ListTile(
    title: ContentText(
      subject == null ? module.title : '$subject: ${module.title}',
    ),
    subtitle: Padding(
      padding: const EdgeInsets.only(top: AppSpacing.xs),
      child: LinearProgressIndicator(value: module.recall),
    ),
    trailing: Explained(
      badgeHelp(moduleBadge(module)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          RecallStat(module.recall),
          const SizedBox(width: AppSpacing.sm),
          ModuleMarkIcon(moduleMark(module)),
        ],
      ),
    ),
  );
}

/// A plan revision: its number and the comment (content).
class RevisionLine extends StatelessWidget {
  /// Creates the line.
  const new(this.revision, {super.key});

  /// The revision.
  final PlanChange revision;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
    child: SpokenLabel(
      semanticLabel: 'rev ${revision.rev}: ${revision.comment}',
      child: Row(
        children: [
          CountBadge(revision.rev, icon: Icons.history),
          const SizedBox(width: AppSpacing.sm),
          Expanded(child: ContentText(revision.comment)),
        ],
      ),
    ),
  );
}

/// A subject's status as a glyph (its old word is the spoken label).
class SubjectStatusIcon extends StatelessWidget {
  /// Creates the glyph.
  const new(this.status, {super.key});

  /// The status.
  final SubjectStatus status;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (icon, color) = switch (status) {
      SubjectStatus.drafting => (Icons.edit_note, AppPalette.warning),
      SubjectStatus.draft => (Icons.fact_check_outlined, scheme.primary),
      SubjectStatus.active => (Icons.play_circle_outline, scheme.primary),
      SubjectStatus.completed => (Icons.verified, AppPalette.success),
      SubjectStatus.reviewOnly => (Icons.replay, scheme.outline),
      SubjectStatus.failed => (Icons.error_outline, scheme.error),
    };
    return Align(
      alignment: Alignment.centerLeft,
      child: SpokenLabel(
        semanticLabel: status.wire.replaceAll('_', ' '),
        child: Icon(icon, color: color),
      ),
    );
  }
}
