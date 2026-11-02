/// Lesson screen pieces: pinned tables, chat bubbles, the answer box.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/sql/lesson_models.dart';
import 'package:tutor/sql/sql_models.dart';
import 'package:tutor/ui/metrics_cap.dart';
import 'package:tutor/ui/sql/data_grid.dart';
import 'package:tutor/ui/sql/rich_md.dart';
import 'package:tutor/ui/sql/table_strip.dart';
import 'package:tutor/ui/sql/task_view.dart';

/// The current tables under a header that folds them, capped by [share].
class PinnedTables extends StatelessWidget {
  /// Creates the header and body.
  const new({
    required this.tables,
    required this.open,
    required this.onToggle,
    this.compact = false,
    this.share = 0.3,
    super.key,
  });

  /// Tables to show.
  final List<SqlTable> tables;

  /// Whether the body is shown.
  final bool open;

  /// Folds or unfolds the body.
  final VoidCallback onToggle;

  /// Typing: only the always-visible [TableStrip], no fold.
  final bool compact;

  /// Largest part of the free height the body may take.
  final double share;

  @override
  Widget build(BuildContext context) {
    if (compact) return TableStrip(tables: tables, share: share);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        InkWell(
          key: const ValueKey('tables-header'),
          onTap: onToggle,
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.md,
              vertical: AppSpacing.sm,
            ),
            child: Row(
              children: [
                const Icon(Icons.table_chart_outlined, semanticLabel: 'Tables'),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    tables.map((t) => t.name).join(', '),
                    overflow: TextOverflow.ellipsis,
                    style: sqlMono,
                  ),
                ),
                Icon(open ? Icons.expand_less : Icons.expand_more),
              ],
            ),
          ),
        ),
        if (open)
          CappedHeight(
            share: share,
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.md,
                0,
                AppSpacing.md,
                AppSpacing.sm,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: tableWidgets(tables),
              ),
            ),
          ),
      ],
    );
  }
}

/// A chat bubble: the learner's on the right, the tutor's on the left.
class BubbleView extends StatelessWidget {
  /// Creates the bubble.
  const new(this.bubble, {super.key});

  /// What to show.
  final Bubble bubble;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final grid = bubble.grid;
    return Align(
      alignment: bubble.mine ? Alignment.centerRight : Alignment.centerLeft,
      child: Padding(
        padding: const EdgeInsets.only(bottom: AppSpacing.sm),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: bubble.mine
                ? scheme.primaryContainer
                : scheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(AppRadius.md),
          ),
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: grid != null
                ? Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.output, semanticLabel: 'Result'),
                      const SizedBox(height: AppSpacing.xs),
                      DataGridView(columns: grid.columns, rows: grid.rows),
                    ],
                  )
                : bubble.mine
                ? SelectableText(bubble.md ?? '')
                : RichMd(bubble.md ?? ''),
          ),
        ),
      ),
    );
  }
}

/// The free-text answer box with its send button.
class AnswerBox extends StatelessWidget {
  /// Creates the box.
  const new({
    required this.controller,
    required this.focus,
    required this.canSend,
    required this.onSend,
    super.key,
  });

  /// The text.
  final TextEditingController controller;

  /// Focus of the field.
  final FocusNode focus;

  /// False while a turn is in flight.
  final bool canSend;

  /// Sends the answer.
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(AppSpacing.sm),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(
          child: TextField(
            key: const ValueKey('answer'),
            controller: controller,
            focusNode: focus,
            minLines: 1,
            maxLines: 5,
            keyboardType: TextInputType.multiline,
            decoration: const InputDecoration(border: OutlineInputBorder()),
          ),
        ),
        const SizedBox(width: AppSpacing.sm),
        ListenableBuilder(
          listenable: controller,
          builder: (context, _) => IconButton.filled(
            key: const ValueKey('send'),
            onPressed: canSend && controller.text.trim().isNotEmpty
                ? onSend
                : null,
            icon: const Icon(Icons.send, semanticLabel: 'Send'),
          ),
        ),
      ],
    ),
  );
}

/// The end of a lesson: a way to the [next] topic, or a check mark.
class LessonEnd extends StatelessWidget {
  /// Creates the footer.
  const new({required this.next, required this.onNext, super.key});

  /// The next topic, null after the last.
  final String? next;

  /// Opens the next topic.
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(AppSpacing.sm),
    child: next == null
        ? const Icon(Icons.check_circle_outline, semanticLabel: 'Done')
        : FilledButton(
            key: const ValueKey('next-topic'),
            onPressed: onNext,
            child: const Icon(Icons.arrow_forward, semanticLabel: 'Next topic'),
          ),
  );
}
