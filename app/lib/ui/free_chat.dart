/// The free-model chat (spec Q8/Q9): the outage banner's and read mode's
/// glyph push a Session that starts with `session_start` + `free: true`.
/// Pushed, never a replacement: a `free_unavailable` failure shows its glyph
/// in that Session, and Back lands on read mode (or Home) untouched.
library;

import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/ui/session/session_screen.dart';

/// Opens a free-model session on [subject] (null: the worker's pick).
Future<void> openFreeChat(
  BuildContext context,
  TutorServices s, {
  String? subject,
}) => Navigator.of(context).push(
  MaterialPageRoute<void>(
    builder: (_) =>
        SessionScreen(services: s, subject: subject, resume: true, free: true),
  ),
);
