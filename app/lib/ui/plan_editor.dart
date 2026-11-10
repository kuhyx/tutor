/// The draft plan's module list with local edits; Save sends `plan_edit`
/// (only when changed and valid), Approve sends `plan_approve` (only when
/// nothing is unsaved).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/plan/plan_ops.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/ui/learn_tiles.dart';
import 'package:tutor/ui/module_dialog.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/icon_field.dart';
import 'package:tutor/widgets/spoken_label.dart';

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
            const LearnHeader(
              Icons.format_list_numbered,
              'Modules (teaching order)',
            ),
            for (final (i, m) in _modules.indexed) _tile(i, m),
            Row(
              children: [
                Expanded(
                  child: FieldLabel(
                    semanticLabel: 'Add a module (title)',
                    child: TextField(
                      controller: _add,
                      decoration: iconDecoration(Icons.add_box_outlined),
                      onSubmitted: (_) => _addModule(),
                    ),
                  ),
                ),
                GlyphButton(
                  icon: Icons.add,
                  semanticLabel: 'Add module',
                  onPressed: _addModule,
                ),
              ],
            ),
            if (problems.isNotEmpty)
              Wrap(
                spacing: AppSpacing.sm,
                children: [
                  for (final p in problems)
                    CueChip(kind: CueKind.error, semanticLabel: p),
                ],
              ),
            const SizedBox(height: AppSpacing.md),
            Wrap(
              alignment: WrapAlignment.end,
              spacing: AppSpacing.sm,
              children: [
                if (_dirty)
                  GlyphButton(
                    icon: Icons.undo,
                    semanticLabel: 'Undo edits',
                    onPressed: () => _set(widget.plan.modules),
                  ),
                GlyphButton(
                  icon: Icons.save_outlined,
                  semanticLabel: 'Save edits',
                  onPressed: _dirty && problems.isEmpty && !busy
                      ? () => widget.onSave(_modules)
                      : null,
                ),
                GlyphButton(
                  icon: Icons.done_all,
                  semanticLabel: 'Approve plan',
                  filled: true,
                  onPressed: _dirty || busy ? null : widget.onApprove,
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
            leading: CountBadge(i + 1),
            title: ContentText(m.title),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (m.summary.isNotEmpty) ContentText(m.summary),
                if (m.requires.isNotEmpty)
                  Row(
                    children: [
                      const Icon(
                        Icons.account_tree_outlined,
                        size: AppTextSize.label,
                        semanticLabel: 'requires',
                      ),
                      const SizedBox(width: AppSpacing.xs),
                      Expanded(child: ContentText(_names(m, names))),
                    ],
                  ),
                if (m.cards > 0)
                  SpokenLabel(
                    semanticLabel: '${m.cards} cards (cannot be removed)',
                    child: Wrap(
                      spacing: AppSpacing.sm,
                      children: [
                        GlyphStat(Icons.style_outlined, '${m.cards}'),
                        const Icon(Icons.lock_outline, size: AppTextSize.label),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          Wrap(
            alignment: WrapAlignment.end,
            children: [
              GlyphButton(
                icon: Icons.arrow_upward,
                semanticLabel: 'Move up',
                onPressed: i == 0
                    ? null
                    : () => _set(moveModule(_modules, i, i - 1)),
              ),
              GlyphButton(
                icon: Icons.arrow_downward,
                semanticLabel: 'Move down',
                onPressed: i == _modules.length - 1
                    ? null
                    : () => _set(moveModule(_modules, i, i + 1)),
              ),
              GlyphButton(
                icon: Icons.edit,
                semanticLabel: 'Edit',
                onPressed: () => _edit(i),
              ),
              GlyphButton(
                icon: Icons.delete_outline,
                semanticLabel: 'Remove',
                onPressed: editable(m)
                    ? () => _set(removeModule(_modules, i))
                    : null,
              ),
            ],
          ),
        ],
      ),
    );
  }
}
