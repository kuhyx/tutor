/// The cards view's progress marks: a subject summary with a bar, and a
/// per-card icon (recalled / done / not taught yet), as the retired page's
/// deck summary and done marks showed them.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/card.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/progress/terms.dart';

/// "x/y done · z recalled · n due" with a done bar; the words explained in
/// a tooltip.
class ProgressSummary extends StatelessWidget {
  /// Creates the summary.
  const new(this.tally, {super.key});

  /// The subject's counts.
  final Tally tally;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Tooltip(
            message: tallyHelp,
            child: Text(
              tally.summary,
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          LinearProgressIndicator(value: tally.taught / tally.cards),
        ],
      ),
    ),
  );
}

/// [child] with the explanation of the progress words it shows (see
/// `progress/terms.dart`) as a tooltip; no tooltip for a null/empty [help].
class Explained extends StatelessWidget {
  /// Creates the wrapper.
  const new(this.help, {required this.child, super.key});

  /// One line per word.
  final String? help;

  /// What the words appear in.
  final Widget child;

  @override
  Widget build(BuildContext context) =>
      (help ?? '').isEmpty ? child : Tooltip(message: help, child: child);
}

/// A card's state as an icon with a tooltip (null: not folded yet).
class CardStateIcon extends StatelessWidget {
  /// Creates the icon.
  const new(this.progress, {super.key});

  /// The card's state.
  final CardProgress? progress;

  @override
  Widget build(BuildContext context) {
    final p = progress;
    final scheme = Theme.of(context).colorScheme;
    final (icon, color, help) = switch (p) {
      null => (Icons.circle_outlined, scheme.outline, null),
      CardProgress(mastered: true) => (
        Icons.star,
        scheme.primary,
        recalledHelp,
      ),
      CardProgress(taught: true) => (
        Icons.check_circle,
        scheme.primary,
        doneHelp,
      ),
      _ => (Icons.radio_button_unchecked, scheme.outline, null),
    };
    return Tooltip(
      message: [?p?.label, ?help].join('\n'),
      child: Icon(icon, color: color),
    );
  }
}

/// The Editor's state word for [card]: how it was suspended, or its progress.
String cardStateWord(StudyCard card, CardProgress? p) => card.removedBySplit
    ? 'Split'
    : card.removedByTutor
    ? 'Removed by tutor'
    : card.restorable
    ? 'Removed'
    : card.suspended
    ? 'suspended'
    : p?.label ?? '';

/// What the Editor's Restore does for a [StudyCard.restorable] card.
String restoreTip(StudyCard card) => card.removedBySplit
    ? 'Undoes the split: the parts go, this card comes back'
    : card.removedUnrecorded
    ? 'Removed before the Editor kept a record: only un-suspends it, '
          'prerequisites are not restored'
    : 'Puts the card and its prerequisites back';
