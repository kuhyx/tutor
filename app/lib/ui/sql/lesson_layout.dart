/// The lesson's frame: tables over the chat (narrow), or beside it (wide).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/sql/sql_models.dart';
import 'package:tutor/ui/fit_layouts.dart';
import 'package:tutor/ui/sql/lesson_parts.dart';
import 'package:tutor/ui/sql/task_view.dart';

/// Tables and chat.
class LessonLayout extends StatelessWidget {
  /// Creates the frame.
  const new({
    required this.wide,
    required this.tables,
    required this.tablesOpen,
    required this.typing,
    required this.onToggle,
    required this.chat,
    super.key,
  });

  /// Side by side.
  final bool wide;

  /// The lesson's tables.
  final List<SqlTable> tables;

  /// The narrow fold is open.
  final bool tablesOpen;

  /// The answer box has focus: only the strip.
  final bool typing;

  /// Folds or unfolds the tables.
  final VoidCallback onToggle;

  /// The chat column.
  final Widget chat;

  @override
  Widget build(BuildContext context) => !wide
      ? Column(
          children: [
            if (tables.isNotEmpty)
              // Phone: shares the height with the chat, never overflows.
              fitFlex(
                context,
                PinnedTables(
                  tables: tables,
                  open: tablesOpen,
                  compact: typing,
                  onToggle: onToggle,
                ),
              ),
            const Divider(height: 1),
            Expanded(child: chat),
          ],
        )
      : Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1360),
            child: Row(
              children: [
                Expanded(
                  flex: 2,
                  child: ListView(
                    key: const ValueKey('tables-pane'),
                    padding: const EdgeInsets.all(AppSpacing.md),
                    children: tableWidgets(tables),
                  ),
                ),
                const VerticalDivider(width: 1),
                Expanded(flex: 3, child: chat),
              ],
            ),
          ),
        );
}
