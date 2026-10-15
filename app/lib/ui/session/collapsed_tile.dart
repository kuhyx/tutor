/// The tutor's latest message while the phone keyboard is open: just its
/// last line, a tap shows the whole message (the keyboard leaves little
/// room, and the last line is usually the ask).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/ui/session/md_text.dart';

/// The last non-blank line of [text] ('' when there is none).
String lastLineOf(String text) => text
    .split('\n')
    .map((l) => l.trimRight())
    .lastWhere((l) => l.trim().isNotEmpty, orElse: () => '');

/// [full] folded to its last line until tapped.
class CollapsedTile extends StatefulWidget {
  /// Creates the tile; [full] is the normal tile, shown once expanded.
  const new({required this.message, required this.full, super.key});

  /// The tutor message.
  final Message message;

  /// The normal, full tile.
  final Widget full;

  @override
  State<CollapsedTile> createState() => _CollapsedTileState();
}

class _CollapsedTileState extends State<CollapsedTile> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final line = lastLineOf(widget.message.text);
    if (_open || line.isEmpty) return widget.full;
    final scheme = Theme.of(context).colorScheme;
    return Semantics(
      button: true,
      label: 'Show the whole tutor message',
      child: InkWell(
        borderRadius: BorderRadius.circular(AppRadius.md),
        onTap: () => setState(() => _open = true),
        child: Container(
          margin: const EdgeInsets.only(bottom: AppSpacing.md),
          padding: const EdgeInsets.all(AppSpacing.sm),
          decoration: BoxDecoration(
            color: scheme.surfaceContainerLow,
            borderRadius: BorderRadius.circular(AppRadius.md),
          ),
          child: Row(
            children: [
              // Selectable text would swallow the tap that expands the tile.
              Expanded(child: IgnorePointer(child: MarkdownText(line))),
              const SizedBox(width: AppSpacing.sm),
              Icon(Icons.expand_more, color: scheme.onSurfaceVariant),
            ],
          ),
        ),
      ),
    );
  }
}
