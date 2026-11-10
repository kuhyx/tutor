/// Home's overflow menu: each entry is a glyph with a spoken label.
library;

import 'package:flutter/material.dart';

/// The menu entries; [compact] adds Refresh (phone), [signOut] the last one.
List<PopupMenuEntry<String>> homeMenuItems({
  required bool compact,
  required bool signOut,
}) => [
  if (compact) _entry('refresh', Icons.refresh, 'Refresh'),
  _entry('mock', Icons.quiz_outlined, 'Mock test'),
  _entry('history', Icons.history, 'History'),
  _entry('progress', Icons.show_chart, 'Progress'),
  _entry('editor', Icons.edit_note, 'Edit cards'),
  _entry('display', Icons.zoom_in, 'Display size'),
  _entry('newcap', Icons.library_add_outlined, 'New cards per day'),
  _entry('report', Icons.bug_report_outlined, 'Report a problem'),
  if (signOut) _entry('signout', Icons.logout, 'Sign out'),
];

PopupMenuItem<String> _entry(String value, IconData icon, String label) =>
    PopupMenuItem<String>(
      value: value,
      child: Icon(icon, semanticLabel: label),
    );
