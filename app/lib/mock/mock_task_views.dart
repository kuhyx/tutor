import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/mock/mock_models.dart';
import 'package:tutor/mock/mock_run_view.dart';
import 'package:tutor/mock/mock_session.dart';
import 'package:tutor/ui/fit_layouts.dart';
import 'package:tutor/ui/metrics_cap.dart';
import 'package:tutor/ui/sql/data_grid.dart';
import 'package:tutor/ui/sql/rich_md.dart';
import 'package:tutor/ui/sql/sql_editor.dart';
import 'package:tutor/ui/sql/table_strip.dart';
import 'package:tutor/ui/sql/task_view.dart';
import 'package:tutor/widgets/code_symbol_bar.dart';

const _gap = SizedBox(height: AppSpacing.md);

/// The page of one task; [editor], [out] and [onRun] only serve typed ones.
Widget mockTaskBody({
  required MockSession session,
  required MockTask task,
  required TextEditingController? editor,
  required MockRun? out,
  required Widget runLine,
  required VoidCallback? onRun,
}) {
  final head = [
    Text(task.title, style: const TextStyle(fontWeight: FontWeight.w700)),
    const SizedBox(height: AppSpacing.sm),
    RichMd(task.prompt),
  ];
  if (!task.section.typed) {
    return Builder(
      builder: (context) => fitList(
        context,
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          ...head,
          if (task.code.isNotEmpty) CodeBlock(task.code),
          _gap,
          for (final (i, o) in task.options.indexed)
            _Option(
              i,
              o,
              selected: session.answers[task.id] == '$i',
              onTap: () {
                session.update(id: task.id, text: '$i');
                unawaited(session.submit(task.id));
              },
            ),
        ],
      ),
    );
  }
  return MetricsBuilder(
    builder: (context) {
      final pinned = task.tables.isNotEmpty && keyboardUp(context);
      final body = [
        ...head,
        Offstage(
          offstage: pinned,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: tableWidgets(task.tables),
          ),
        ),
        if (task.sample.isNotEmpty) ...[
          _gap,
          const Icon(Icons.flag_outlined, semanticLabel: 'Sample'),
          DataGridView(columns: const [], rows: task.sample),
        ],
        _gap,
        SqlEditor(controller: editor!),
        _gap,
      ];
      final after = [runLine, if (out != null) MockRunView(out)];
      return WithSymbolBar(
        controller: editor,
        show: true,
        child: Column(
          children: [
            if (pinned) fitFlex(context, TableStrip(tables: task.tables)),
            Expanded(
              key: const ValueKey('task-list'),
              // Phone: the task pages; Run and Submit stay above the
              // keyboard. Desktop: one list, buttons under the editor.
              child: fitForm(
                context,
                fields: [...body, ...after],
                bar: [_buttons(session, task, onRun)],
                wide: (_) => ListView(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  keyboardDismissBehavior:
                      ScrollViewKeyboardDismissBehavior.onDrag,
                  children: [...body, _buttons(session, task, onRun), ...after],
                ),
              ),
            ),
          ],
        ),
      );
    },
  );
}

Widget _buttons(MockSession session, MockTask task, VoidCallback? onRun) => Row(
  children: [
    FilledButton.tonal(
      key: const ValueKey('run'),
      onPressed: onRun,
      child: const Icon(Icons.play_arrow, semanticLabel: 'Run'),
    ),
    const SizedBox(width: AppSpacing.sm),
    FilledButton(
      key: const ValueKey('submit'),
      onPressed: () => session.submit(task.id),
      child: Icon(
        session.isSubmitted(task.id) ? Icons.check : Icons.send,
        semanticLabel: 'Submit',
      ),
    ),
  ],
);

class _Option extends StatelessWidget {
  const new(this.i, this.text, {required this.selected, required this.onTap});

  final int i;
  final String text;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Material(
        color: selected ? scheme.primaryContainer : scheme.surface,
        shape: RoundedRectangleBorder(
          side: BorderSide(color: selected ? scheme.primary : scheme.outline),
          borderRadius: BorderRadius.circular(AppRadius.sm),
        ),
        child: InkWell(
          key: ValueKey('opt-$i'),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Row(
              children: [
                Icon(
                  selected
                      ? Icons.radio_button_checked
                      : Icons.radio_button_unchecked,
                  size: 20,
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(child: Text(text, style: sqlMono)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
