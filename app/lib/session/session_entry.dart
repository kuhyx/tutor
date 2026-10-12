/// What Home's session button opens. New material comes from
/// `prefs.current_subject`, so the button continues THAT subject: `live`
/// only when it is a session of it, else the worker is asked for the
/// subject's open session (`session_start` with `resume`), else its next
/// card (kuhy, 2026-10-12: Continue in automation opened a car session).
library;

import 'package:tutor/model/root.dart';

/// The Session screen's target.
class SessionEntry {
  /// Creates the target.
  const new({required this.label, this.subject, this.resume = false});

  /// Button label.
  final String label;

  /// Follow only this subject's live session (null: whatever is live).
  final String? subject;

  /// Ask the worker for [subject]'s open session on opening.
  final bool resume;
}

/// Home's session button for [live] and [current] (`prefs.current_subject`).
SessionEntry sessionEntry(Live? live, String? current) {
  if (current == null) {
    return SessionEntry(label: live == null ? 'Learn' : 'Continue session');
  }
  if (live?.subject == current) {
    return SessionEntry(label: 'Continue session', subject: current);
  }
  return SessionEntry(
    label: 'Continue learning',
    subject: current,
    resume: true,
  );
}
