/// Opens read mode (`ui/read_screen.dart`); its own file because `nav.dart`
/// is at the file-length cap.
library;

import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/ui/read_screen.dart';

/// Opens read mode: new cards with no model. [subject] keeps it to one
/// subject (null: every subject), [unavailable] shows the outage glyph at
/// once, and [onFreeChat] backs the free-chat glyph (null: no glyph).
Future<void> openRead(
  BuildContext context,
  TutorServices services, {
  String? subject,
  Unavailable? unavailable,
  VoidCallback? onFreeChat,
}) => Navigator.of(context).push(
  MaterialPageRoute<void>(
    builder: (_) => ReadScreen(
      services: services,
      subject: subject,
      unavailable: unavailable,
      onFreeChat: onFreeChat,
    ),
  ),
);
