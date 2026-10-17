/// The progress words the UI uses, each with its one-line explanation (shown
/// as a tooltip wherever a counter or badge uses the word). "Mastered" is
/// never shown: the persisted `mastered` module status reads "reviewed".
library;

import 'package:tutor/model/plan.dart';
import 'package:tutor/progress/card_progress.dart';

/// Done = taught.
const doneHelp = 'Done: the tutor taught you this card';

/// A module is done once every card of it is taught.
const doneModuleHelp = 'Done: the tutor taught you every card of this module';

/// Known = the concepts list of the session side panel.
const knownHelp = 'Known: concepts you used correctly with the tutor';

/// Recalled = `good` (curriculum §6), per card.
const recalledHelp =
    'Recalled: you answered it right at least 20 h after learning it';

/// Reviewed = the module unlock.
const reviewedModuleHelp =
    'Reviewed: every card got Good in review — the next module is open';

/// [m]'s badge: "reviewed" once the PC marked it `mastered` or every card
/// got Good ([review]); "done" once every card is taught; else its status
/// (locked, generating, ready, failed). Failed always shows (Retry).
String moduleBadge(Module m, [ModuleReview? review]) {
  if (m.status == ModuleStatus.failed) return m.status.name;
  if (m.status == ModuleStatus.mastered || review == ModuleReview.reviewed) {
    return 'reviewed';
  }
  return review == ModuleReview.done ? 'done' : m.status.name;
}

/// The explanation for a [moduleBadge] word, or null for the plain statuses.
String? badgeHelp(String badge) => switch (badge) {
  'reviewed' => reviewedModuleHelp,
  'done' => doneModuleHelp,
  _ => null,
};

/// The explanations for a "x done · y recalled" counter, one per line.
const tallyHelp = '$doneHelp\n$recalledHelp';
