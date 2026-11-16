/// The composer's drafts: which questions the latest message asks, the key
/// they are saved under, and how a late draft or typing opens the fields.
library;

import 'package:flutter/widgets.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/session/session_feed.dart';

/// The questions [latest] asks (none unless it is a tutor message).
List<Asked> askedIn(KeyedMessage? latest) =>
    latest != null && latest.message.role == 'tutor'
    ? askedOf(latest.message)
    : const [];

/// The draft's storage key for session [sid] and its [latest] message.
String draftKeyFor(String sid, KeyedMessage? latest) => askedIn(latest).isEmpty
    ? plainDraftKey(sid)
    : answersDraftKey(sid, latest!.key);

/// Adds to [opened] every question whose box holds own words (not a tapped
/// choice): its field stays open from then on, even when they are deleted.
void latchOwnWords(
  List<TextEditingController> boxes,
  List<Asked> asked,
  Set<int> opened,
) {
  for (final (i, b) in boxes.indexed) {
    if (i < asked.length &&
        b.text.isNotEmpty &&
        !asked[i].choices.contains(b.text)) {
      opened.add(i);
    }
  }
}

/// Fills each box of [boxes] that is still empty from the draft [saved], so
/// a draft read that lands late never overwrites what was typed meanwhile.
/// Extra entries (an old draft's comment box) are ignored.
void fillEmptyBoxes(List<TextEditingController> boxes, List<String> saved) {
  for (final (i, v) in saved.indexed) {
    if (i < boxes.length && boxes[i].text.isEmpty) boxes[i].text = v;
  }
}

/// The step to resume on: the first of [questions] boxes still empty, else
/// the last.
int resumeStep(List<TextEditingController> boxes, int questions) {
  for (var i = 0; i < questions; i++) {
    if (boxes[i].text.isEmpty) return i;
  }
  return questions - 1;
}
