/// Per-question answer boxes, ported from `static/questions.js`.
///
/// Each question of the latest tutor message (its own `questions`, then the
/// comprehension check, numbered on so the reply's Q1, Q2... match the
/// boxes) gets a box. Together they are sent as ONE `message` text.
library;

import 'package:tutor/model/json.dart';
import 'package:tutor/model/message.dart';

/// One question shown with an answer box.
class Asked {
  /// Creates the question.
  const new({
    required this.label,
    required this.text,
    this.check = false,
    this.choices = const [],
  });

  /// `Q1`, `Q2`, ...
  final String label;

  /// Question text.
  final String text;

  /// The comprehension check (shown with its own label).
  final bool check;

  /// Tap-to-fill answers the tutor suggests (empty: none).
  final List<String> choices;

  /// Label as shown above the box.
  String get heading => check ? '$label - Comprehension check' : label;
}

/// What [m] asks, in box order.
List<Asked> askedOf(Message m) {
  final texts = [
    for (final q in m.questions) (q, false),
    if (_checkText(m.check) case final c?) (c, true),
  ];
  return [
    for (final (n, (text, check)) in texts.indexed)
      Asked(
        label: 'Q${n + 1}',
        text: text,
        check: check,
        choices: check
            ? m.checkChoices
            : (n < m.choices.length ? m.choices[n] : const []),
      ),
  ];
}

String? _checkText(Json? check) {
  final q = check?['question'];
  return q is String && q.trim().isNotEmpty ? q : null;
}

/// Ends an answer a tapped choice filled and nobody edited, so the server
/// tells a tap from a typed answer (`tutor/picked.py`): a tap alone never
/// passes the comprehension check.
const pickedMarker = '(picked option)';

/// The one message the boxes send: `Q1: ...` / `A: ...` per question.
/// [values] has one entry per question; extra entries (an old draft's
/// "own comment" box) are ignored. Empty when nothing was typed. Only
/// trailing space is cut, so an indented first line of code keeps its
/// indent. A box still holding exactly one of
/// its question's choices gets [pickedMarker] (stateless, so a reloaded
/// draft keeps it; a choice typed word for word is as cued as a tap).
String composeAnswers(List<Asked> asked, List<String> values) {
  String at(int i) {
    final v = i < values.length ? values[i].trimRight() : '';
    if (v.trim().isEmpty) return '';
    final tap = asked[i].choices.contains(v.trim());
    return tap ? '${v.trim()} $pickedMarker' : v;
  }

  if (List.generate(asked.length, at).every((v) => v.isEmpty)) return '';
  final blocks = [
    for (final (n, a) in asked.indexed)
      '${a.label}: ${a.text}\nA: ${at(n).isEmpty ? '(skipped)' : at(n)}',
  ];
  return blocks.join('\n\n');
}

/// What each box of [asked] starts with when the boxes are rebuilt: the
/// text [typed] (box order of [before]) for the same question, so a
/// re-keyed message never drops an answer; else empty. No questions: the
/// one plain box, empty.
List<String> carriedAnswers(
  List<Asked> before,
  List<String> typed,
  List<Asked> asked,
) => asked.isEmpty
    ? ['']
    : [
        for (final a in asked)
          switch (before.indexWhere((b) => b.text == a.text)) {
            final i when i >= 0 && i < typed.length => typed[i],
            _ => '',
          },
      ];

/// The question texts of [asked], in box order.
List<String> textsOf(List<Asked> asked) => [for (final a in asked) a.text];

/// Local draft key for the boxes of message [msgKey] in session [sid]
/// (drafts survive a reload; dropped once the answers are sent).
String answersDraftKey(String sid, String msgKey) =>
    'draft.answers.$sid.$msgKey';

/// Local draft key for the plain answer box of session [sid].
String plainDraftKey(String sid) => 'draft.text.$sid';
