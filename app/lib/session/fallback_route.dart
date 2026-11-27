/// Where Start goes while Claude is out (kuhy, 2026-11-26; plan e79be0be-0
/// step 2): due cards in the scope Start was pressed for -> the FSRS Review
/// (due queue only); else an untaught drafted card -> read mode; else a
/// taught card -> the drill; else read mode's empty glyph.
///
/// The sources, so that no new server kind is needed and none of them can
/// disagree with the screen it opens:
/// - due: `dueItems`, the exact queue the Review screen opens (local log);
/// - untaught: a `read_next` probe. The worker applies the rules the app
///   does not mirror (unlocked, open, not C3-refused, not flagged,
///   prerequisites taught), and pregenerated cards sit in locked modules, so
///   the catalog alone would send kuhy to an empty read mode. The probe only
///   opens a prompt (read mode asks again and gets the same card); a failed
///   probe opens read mode anyway, whose failed stage offers a retry;
/// - taught: the local fold (`scheduled`, minus flagged and suspended).
library;

import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/drill/read_models.dart';
import 'package:tutor/model/outage_window.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/review/review_items.dart';
import 'package:tutor/session/session_entry.dart';
import 'package:tutor/ui/free_chat.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/nav_read.dart';

export 'package:tutor/session/session_entry.dart' show SessionEntry;
export 'package:tutor/ui/free_chat.dart' show openFreeChat;

/// The chooser's four answers.
enum FallbackRoute {
  /// The FSRS Review on the due queue.
  review,

  /// Read mode on the next untaught card.
  read,

  /// The drill on taught cards.
  drill,

  /// Nothing at all: read mode's empty glyph.
  empty,
}

/// The order itself: [due] cards, [readable] (an untaught card to read),
/// [taught] (a card the drill can ask).
FallbackRoute chooseFallback({
  required int due,
  required bool readable,
  required bool taught,
}) => due > 0
    ? FallbackRoute.review
    : readable
    ? FallbackRoute.read
    : taught
    ? FallbackRoute.drill
    : FallbackRoute.empty;

/// [window] as the drill's and read mode's outage value.
Unavailable unavailableOf(OutageWindow window) =>
    Unavailable(until: window.until, reason: window.reason.wire);

/// Gathers the facts for [subject] (null: every subject) and decides; the
/// probe goes through [runner] when given (its status shows meanwhile).
Future<FallbackRoute> decideFallback(
  TutorServices s, {
  String? subject,
  RequestRunner? runner,
  DateTime Function() now = DateTime.now,
}) async {
  final due = await dueItems(
    catalog: s.catalog,
    events: s.events,
    now: now().toUtc(),
    subject: subject,
  );
  if (due.isNotEmpty) return FallbackRoute.review;
  if (await _readable(s, subject, runner)) return FallbackRoute.read;
  final folded = await foldAll(s.events, s.catalog);
  final infos = cardInfos((await s.catalog.cached()).values);
  final taught = folded.scheduled.keys.any(
    (key) =>
        (subject == null || key.startsWith('$subject/')) &&
        !folded.flagged.contains(key) &&
        !(infos[key]?.suspended ?? true),
  );
  return chooseFallback(due: 0, readable: false, taught: taught);
}

// A failed or unsent probe counts as readable: read mode shows why.
Future<bool> _readable(
  TutorServices s,
  String? subject,
  RequestRunner? shared,
) async {
  final runner = shared ?? RequestRunner(s.relay);
  try {
    final status = await runner.run(readNext(subject: subject));
    if (status is! RelayDone) return true;
    return ReadNext.fromJson(status.data) is! ReadEmpty;
  } on FormatException {
    return true;
  } finally {
    // Not awaited, as every one-shot runner: dispose waits on the stream.
    if (shared == null) unawaited(runner.dispose());
  }
}

/// Runs the chooser and opens its screen; [unavailable] is the outage the
/// screen shows at once.
Future<void> openFallback(
  BuildContext context,
  TutorServices s, {
  String? subject,
  Unavailable? unavailable,
  RequestRunner? runner,
  DateTime Function() now = DateTime.now,
}) async {
  final route = await decideFallback(
    s,
    subject: subject,
    runner: runner,
    now: now,
  );
  if (!context.mounted) return;
  final title = subject == null
      ? null
      : (await s.catalog.cached())[subject]?.meta.title;
  if (!context.mounted) return;
  await switch (route) {
    FallbackRoute.review => openReview(
      context,
      s,
      subject: subject,
      subjectTitle: title,
      unavailable: unavailable,
    ),
    FallbackRoute.drill => openReview(
      context,
      s,
      drill: true,
      subject: subject,
      subjectTitle: title,
      unavailable: unavailable,
    ),
    FallbackRoute.read || FallbackRoute.empty => openRead(
      context,
      s,
      subject: subject,
      unavailable: unavailable,
      onFreeChat: () => unawaited(openFreeChat(context, s, subject: subject)),
    ),
  };
}

/// Home's Start ([entry]): while [today]'s outage is open at [now], the
/// chooser over every subject (kuhy: Home's main Start covers them all),
/// with no chat request first; else the Session as before. A live session
/// (a free chat among them) still opens: that button sends nothing.
Future<void> openStart(
  BuildContext context,
  TutorServices s,
  SessionEntry entry, {
  Today? today,
  RequestRunner? runner,
  DateTime Function() now = DateTime.now,
}) {
  final window = today?.outageAt(now());
  if (window == null || entry.kind == SessionKind.live) {
    return openSession(context, s, entry: entry);
  }
  // Back on Home: a failed probe's cue on the shared runner is stale.
  return openFallback(
    context,
    s,
    unavailable: unavailableOf(window),
    runner: runner,
    now: now,
  ).whenComplete(() => runner?.clear());
}
