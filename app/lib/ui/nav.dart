/// Opening screens, and the route strings fixture builds and deep links use
/// (`/plan/<subject>`, `/session`, `/history`, `/history/<sid>`,
/// `/progress`, `/editor[/<subject>]`, `/review`, `/drill`, `/report`;
/// `/session/continue` opens the Session and asks for the open session).
library;

import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/session/session_entry.dart';
import 'package:tutor/ui/editor_screen.dart';
import 'package:tutor/ui/history_screen.dart';
import 'package:tutor/ui/plan_screen.dart';
import 'package:tutor/ui/progress_screen.dart';
import 'package:tutor/ui/report_dialog.dart';
import 'package:tutor/ui/review_screen.dart';
import 'package:tutor/ui/session/session_screen.dart';
import 'package:tutor/ui/transcript_screen.dart';

Future<void> _push(
  BuildContext context,
  Widget screen, {
  bool replace = false,
}) {
  final route = MaterialPageRoute<void>(builder: (_) => screen);
  final nav = Navigator.of(context);
  return replace ? nav.pushReplacement(route) : nav.push(route);
}

/// Opens the Session (the live one, or Start); [entry] (Home) keeps it on
/// one subject and may first ask for that subject's open session.
Future<void> openSession(
  BuildContext context,
  TutorServices s, {
  SessionEntry? entry,
  bool replace = false,
}) => _push(
  context,
  SessionScreen(
    services: s,
    subject: entry?.subject,
    resume: entry?.resume ?? false,
  ),
  replace: replace,
);

/// Opens [subject]'s plan.
Future<void> openPlan(BuildContext context, TutorServices s, String subject) =>
    _push(context, PlanScreen(services: s, subject: subject));

/// Opens History.
Future<void> openHistory(BuildContext context, TutorServices s) =>
    _push(context, HistoryScreen(services: s));

/// Opens a past session.
Future<void> openTranscript(
  BuildContext context,
  TutorServices s,
  String sid,
) => _push(context, TranscriptScreen(services: s, sid: sid));

/// Opens Progress.
Future<void> openProgress(BuildContext context, TutorServices s) =>
    _push(context, ProgressScreen(services: s));

/// Opens the card editor.
Future<void> openEditor(
  BuildContext context,
  TutorServices s, {
  String? subject,
}) => _push(context, EditorScreen(services: s, subject: subject));

/// Opens Review; [drill] starts in Drill mode (pick-an-answer, no model),
/// with [unavailable] as the "Claude limit" banner; [module] reviews that
/// module's taught cards instead of the due queue.
Future<void> openReview(
  BuildContext context,
  TutorServices s, {
  bool drill = false,
  Unavailable? unavailable,
  ModuleRef? module,
  bool replace = false,
}) => _push(
  context,
  ReviewScreen(
    services: s,
    drill: drill,
    unavailable: unavailable,
    module: module,
  ),
  replace: replace,
);

/// Shows "Report a problem".
Future<void> showReport(
  BuildContext context,
  TutorServices s, {
  required String route,
  String? session,
  String? msg,
  String? preview,
}) => showDialog<void>(
  context: context,
  builder: (_) => ReportDialog(
    sender: s.feedback,
    route: route,
    session: session,
    msg: msg,
    preview: preview,
  ),
);

/// Opens [route] (see the library doc); unknown routes do nothing.
Future<void> openRoute(BuildContext context, TutorServices s, String route) {
  final parts = route.split('/').where((p) => p.isNotEmpty).toList();
  final arg = parts.length > 1 ? parts[1] : null;
  return switch (parts.firstOrNull) {
    'plan' when arg != null => openPlan(context, s, arg),
    'session' when arg == 'continue' => openSession(
      context,
      s,
      entry: const SessionEntry(label: 'Continue', resume: true),
    ),
    'session' => openSession(context, s),
    'history' when arg != null => openTranscript(context, s, arg),
    'history' => openHistory(context, s),
    'progress' => openProgress(context, s),
    'editor' => openEditor(context, s, subject: arg),
    'review' => openReview(context, s),
    'drill' => openReview(context, s, drill: true),
    'report' => showReport(context, s, route: '/'),
    _ => Future<void>.value(),
  };
}
