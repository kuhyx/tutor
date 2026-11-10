/// What Home's session button opens. New material comes from
/// `prefs.current_subject`, so the button continues THAT subject: `live`
/// only when it is a session of it, else the worker is asked for the
/// subject's open session (`session_start` with `resume`), else its next
/// card (kuhy, 2026-10-12: Continue in automation opened a car session).
library;

import 'package:tutor/model/root.dart';

/// Which button Home shows (a glyph each; its words are spoken only).
enum SessionKind {
  /// No current subject and nothing live: start learning.
  learn('Learn'),

  /// A live session (of the current subject, if one is picked).
  live('Continue session'),

  /// Ask the worker for the subject's open session or next card.
  resume('Continue learning');

  new(this.semanticLabel);

  /// What a screen reader (and the browser drivers) call the button.
  final String semanticLabel;
}

/// The Session screen's target.
class SessionEntry {
  /// Creates the target.
  const new({required this.kind, this.subject, this.resume = false});

  /// Which button it is.
  final SessionKind kind;

  /// The button's spoken label.
  String get semanticLabel => kind.semanticLabel;

  /// Follow only this subject's live session (null: whatever is live).
  final String? subject;

  /// Ask the worker for [subject]'s open session on opening.
  final bool resume;
}

/// Home's session button for [live] and [current] (`prefs.current_subject`).
SessionEntry sessionEntry(Live? live, String? current) {
  if (current == null) {
    return SessionEntry(
      kind: live == null ? SessionKind.learn : SessionKind.live,
    );
  }
  if (live?.subject == current) {
    return SessionEntry(kind: SessionKind.live, subject: current);
  }
  return SessionEntry(kind: SessionKind.resume, subject: current, resume: true);
}
