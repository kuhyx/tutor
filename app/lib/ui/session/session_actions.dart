/// The Session AppBar's buttons: copy the session id; on narrow windows,
/// open the side panel drawer.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// The AppBar actions; [sid] is null until a session shows.
List<Widget> sessionActions({required String? sid, required bool wide}) => [
  if (sid != null)
    Builder(
      builder: (context) => IconButton(
        tooltip: 'Copy session id',
        onPressed: () => _copy(context, sid),
        icon: const Icon(Icons.copy_outlined),
      ),
    ),
  if (!wide)
    Builder(
      builder: (context) => IconButton(
        tooltip: 'Card and progress',
        onPressed: Scaffold.of(context).openEndDrawer,
        icon: const Icon(Icons.view_sidebar_outlined),
      ),
    ),
];

Future<void> _copy(BuildContext context, String sid) async {
  final messenger = ScaffoldMessenger.of(context);
  await Clipboard.setData(ClipboardData(text: sid));
  messenger.showSnackBar(const SnackBar(content: Text('Session id copied')));
}
