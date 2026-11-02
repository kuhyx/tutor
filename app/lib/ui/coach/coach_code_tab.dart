import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/coach/coach_models.dart';
import 'package:tutor/ui/coach/coach_run_view.dart';
import 'package:tutor/ui/coach/coach_session.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/sql/sql_editor.dart';

/// The code tab: language, editor with line numbers, Run, per-example
/// results. `touch` adds the symbol row a phone keyboard lacks.
class CoachCodeTab extends StatelessWidget {
  /// Creates the tab.
  const new({required this.session, required this.touch, super.key});

  /// The session.
  final CoachSession session;

  /// A touch screen.
  final bool touch;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: Listenable.merge([session, session.code]),
    builder: (context, _) {
      final s = session;
      final langs = s.opened?.langs ?? [s.lang];
      final report = s.report;
      return ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
        children: [
          DropdownButton<String>(
            key: const ValueKey('lang'),
            value: langs.contains(s.lang) ? s.lang : null,
            items: [
              for (final l in langs)
                DropdownMenuItem(value: l, child: Text(coachLangs[l] ?? l)),
            ],
            onChanged: (l) => l == null ? null : s.setLang(l),
          ),
          const SizedBox(height: AppSpacing.sm),
          SqlEditor(
            controller: s.code,
            showKeys: touch,
            symbols: isSqlLang(s.lang) ? sqlSymbols : codeSymbols,
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              RunnerBuilder(
                s.runs,
                (_) => FilledButton(
                  key: const ValueKey('run'),
                  onPressed: s.runs.canSend && s.code.text.trim().isNotEmpty
                      ? s.run
                      : null,
                  child: const Icon(Icons.play_arrow, semanticLabel: 'Run'),
                ),
              ),
            ],
          ),
          RequestStatusLine(s.runs),
          if (report != null && report.held && s.note != null)
            Text(s.note!, key: const ValueKey('run-note')),
          if (report != null && !report.held)
            CoachRunView(report, key: ObjectKey(report)),
        ],
      );
    },
  );
}
