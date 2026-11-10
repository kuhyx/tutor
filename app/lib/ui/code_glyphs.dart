/// One glyph per machine code (DOCS-contract §4a, `model/codes.dart`), so a
/// cause is visible without words. Every map has a fallback: `other` (an
/// unknown or missing code) paints today's generic glyph, an unknown phase
/// a neutral one. The worker's sentence stays the spoken label.
library;

import 'package:flutter/material.dart';
import 'package:tutor/model/codes.dart';
import 'package:tutor/model/request.dart';

/// The generic error glyph (`CueKind.error`'s default).
const IconData genericErrorIcon = Icons.error_outline;

/// The generic card-edit notice glyph.
const IconData genericNoticeIcon = Icons.edit_note;

/// The glyph of a worker phase; [Phase.other] is neutral.
IconData phaseIcon(Phase phase) => switch (phase) {
  Phase.claimed => Icons.inbox_outlined,
  Phase.thinking => Icons.psychology_outlined,
  Phase.images => Icons.image_search,
  Phase.checkingImages => Icons.fact_check_outlined,
  Phase.publishing => Icons.publish,
  Phase.other => Icons.more_horiz,
};

/// Why Claude is out; [UnavailableReason.other] keeps the old bolt.
IconData unavailableIcon(UnavailableReason reason) => switch (reason) {
  UnavailableReason.rateLimit => Icons.hourglass_bottom,
  UnavailableReason.overloaded => Icons.dns_outlined,
  UnavailableReason.network => Icons.wifi_off,
  UnavailableReason.other => Icons.bolt_outlined,
};

/// The glyph of a non-blocking failure [code] (blocking codes have their
/// call-to-action glyph, `relay_cue.dart`); null = the generic error glyph.
IconData? relayCodeIcon(RelayCode code) => switch (code) {
  RelayCode.badRequest => Icons.rule,
  RelayCode.notLive => Icons.link_off,
  RelayCode.sessionLive => Icons.dynamic_feed_outlined,
  RelayCode.unknownCard => Icons.search_off,
  RelayCode.planConflict => Icons.difference_outlined,
  RelayCode.editRefused => Icons.edit_off,
  RelayCode.focusRefused => Icons.timer_off_outlined,
  RelayCode.modelError => Icons.psychology_alt,
  RelayCode.claudeUnavailable => Icons.bolt_outlined,
  RelayCode.unknownPrompt => Icons.quiz_outlined,
  RelayCode.gaveUp => Icons.running_with_errors,
  RelayCode.workerError => Icons.desktop_access_disabled,
  RelayCode.locked ||
  RelayCode.dailyNewCap ||
  RelayCode.noCardLeft ||
  RelayCode.other => null,
};

/// A failure's glyph from its code, `reason` and `error_kind`: the reason
/// wins (paste the statement; which outage), then the code; null = generic.
IconData? failureIcon({
  required RelayCode code,
  FailReason reason = FailReason.other,
}) => switch (reason) {
  FailReason.pasteStatement => Icons.content_paste,
  FailReason.rateLimit => unavailableIcon(UnavailableReason.rateLimit),
  FailReason.overloaded => unavailableIcon(UnavailableReason.overloaded),
  FailReason.network => unavailableIcon(UnavailableReason.network),
  FailReason.other => relayCodeIcon(code),
};

/// Why a subject draft or a module's cards failed; [ErrorKind.other] is the
/// generic error glyph.
IconData errorKindIcon(ErrorKind kind) => switch (kind) {
  ErrorKind.claudeLimit => unavailableIcon(UnavailableReason.rateLimit),
  ErrorKind.claudeOverloaded => unavailableIcon(UnavailableReason.overloaded),
  ErrorKind.claudeNetwork => unavailableIcon(UnavailableReason.network),
  ErrorKind.modelFailed => Icons.psychology_alt,
  ErrorKind.sourcesMissing => Icons.travel_explore,
  ErrorKind.tooFewCards => Icons.filter_alt_off_outlined,
  ErrorKind.badRequest => Icons.rule,
  ErrorKind.other => genericErrorIcon,
};

/// What a card edit did; [NoticeKind.other] (an older message) is generic.
IconData noticeIcon(NoticeKind kind) => switch (kind) {
  NoticeKind.removed => Icons.delete_outline,
  NoticeKind.added => Icons.add_card,
  NoticeKind.updated => Icons.edit_outlined,
  NoticeKind.split => Icons.call_split,
  NoticeKind.mnemonicSet => Icons.tips_and_updates_outlined,
  NoticeKind.mnemonicCleared => Icons.backspace_outlined,
  NoticeKind.other => genericNoticeIcon,
};

/// Why the clock paused; [PauseReason.other] is the plain pause glyph.
IconData pauseIcon(PauseReason reason) => switch (reason) {
  PauseReason.lowEffort => Icons.sentiment_dissatisfied_outlined,
  PauseReason.stalled => Icons.hourglass_disabled,
  PauseReason.other => Icons.pause_circle_outline,
};
