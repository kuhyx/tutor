/// The draft plan's module list with local edits; Save sends `plan_edit`
/// (only when changed and valid), Approve sends `plan_approve` (only when
/// nothing is unsaved).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/plan/plan_ops.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/ui/module_dialog.dart';

/// Editable module list.
class PlanEditor extends StatefulWidget {
  /// Creates the editor.
  const new({
    required this.plan,
    required this.busy,
    required this.onSave,
    required this.onApprove,
    this.onDirty,
    super.key,
  });

  /// The plan as the worker wrote it.
  final Plan plan;

  /// Request status (buttons are off while one is in flight).
  final ValueNotifier<RelayStatus?> busy;

  /// Sends the edited modules.
  final ValueChanged<List<Module>> onSave;

  /// Approves the plan as it is.
  final VoidCallback onApprove;

  /// Told after each local change whether edits are unsaved.
  final ValueChanged<bool>? onDirty;

  @override
  State<PlanEditor> createState() => _PlanEditorState();
}

class _PlanEditorState extends State<PlanEditor> {
  late List<Module> _modules = widget.plan.modules;
  final _add = TextEditingController();

  bool get _dirty => !identical(_modules, widget.plan.modules);

  @override
  void dispose() {
    _add.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(PlanEditor old) {
    super.didUpdateWidget(old);
    // A refetch of the same plan rev: follow it unless kuhy has edits.
    if (identical(_modules, old.plan.modules)) _modules = widget.plan.modules;
  }

  void _set(List<Module> next) {
    setState(() => _modules = next);
    widget.onDirty?.call(_dirty);
  }

  Future<void> _edit(int i) async {
    final edit = await editModuleDialog(
      context,
      _modules[i],
      _modules.take(i).toList(),
    );
    if (edit == null || !mounted) return;
    _set(
      setRequires(
        renameModule(_modules, i, edit.title, summary: edit.summary),
        i,
        edit.requires,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final problems = planProblems(_modules);
    return ValueListenableBuilder<RelayStatus?>(
      valueListenable: widget.busy,
      builder: (context, status, _) {
        final busy = status is RelayQueued || status is RelayWorking;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SectionHeader('Modules (teaching order)'),
            for (final (i, m) in _modules.indexed) _tile(i, m),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _add,
                    decoration: const InputDecoration(
                      labelText: 'Add a module (title)',
                    ),
                    onSubmitted: (_) => _addModule(),
                  ),
                ),
                IconButton(
                  tooltip: 'Add module',
                  onPressed: _addModule,
                  icon: const Icon(Icons.add),
                ),
              ],
            ),
            for (final p in problems)
              Text(
                p,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            const SizedBox(height: AppSpacing.md),
            Wrap(
              alignment: WrapAlignment.end,
              spacing: AppSpacing.sm,
              children: [
                if (_dirty)
                  TextButton(
                    onPressed: () => _set(widget.plan.modules),
                    child: const Text('Undo edits'),
                  ),
                OutlinedButton(
                  onPressed: _dirty && problems.isEmpty && !busy
                      ? () => widget.onSave(_modules)
                      : null,
                  child: const Text('Save edits'),
                ),
                FilledButton(
                  onPressed: _dirty || busy ? null : widget.onApprove,
                  child: const Text('Approve plan'),
                ),
              ],
            ),
          ],
        );
      },
    );
  }

  static String _names(Module m, Map<String, String> names) =>
      m.requires.map((r) => names[r] ?? r).join(', ');

  void _addModule() {
    final t = _add.text.trim();
    if (t.isEmpty) return;
    _set(addModule(_modules, t));
    _add.clear();
  }

  Widget _tile(int i, Module m) {
    final names = {for (final x in _modules) x.id: x.title};
    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ListTile(
            title: Text('${i + 1}. ${m.title}'),
            subtitle: Text(
              [
                if (m.summary.isNotEmpty) m.summary,
                if (m.requires.isNotEmpty) 'requires: ${_names(m, names)}',
                if (m.cards > 0) '${m.cards} cards (cannot be removed)',
              ].join('\n'),
            ),
          ),
          Wrap(
            alignment: WrapAlignment.end,
            children: [
              IconButton(
                tooltip: 'Move up',
                onPressed: i == 0
                    ? null
                    : () => _set(moveModule(_modules, i, i - 1)),
                icon: const Icon(Icons.arrow_upward),
              ),
              IconButton(
                tooltip: 'Move down',
                onPressed: i == _modules.length - 1
                    ? null
                    : () => _set(moveModule(_modules, i, i + 1)),
                icon: const Icon(Icons.arrow_downward),
              ),
              IconButton(
                tooltip: 'Edit',
                onPressed: () => _edit(i),
                icon: const Icon(Icons.edit),
              ),
              IconButton(
                tooltip: 'Remove',
                onPressed: editable(m)
                    ? () => _set(removeModule(_modules, i))
                    : null,
                icon: const Icon(Icons.delete_outline),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
