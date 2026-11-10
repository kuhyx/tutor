import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/coach/coach_models.dart';
import 'package:tutor/ui/coach/coach_run_view.dart';
import 'package:tutor/ui/coach/coach_session.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/fit_layouts.dart';
import 'package:tutor/ui/fit_pages.dart';
import 'package:tutor/ui/layout.dart';
import 'package:tutor/ui/sql/problem_cue.dart';
import 'package:tutor/ui/sql/sql_editor.dart';
import 'package:tutor/widgets/code_symbol_bar.dart';
import 'package:tutor/widgets/content_text.dart';

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
      final run = RunnerBuilder(
        s.runs,
        (_) => FilledButton(
          key: const ValueKey('run'),
          onPressed: s.runs.canSend && s.code.text.trim().isNotEmpty
              ? s.run
              : null,
          child: const Icon(Icons.play_arrow, semanticLabel: 'Run'),
        ),
      );
      final top = [
        DropdownButton<String>(
          key: const ValueKey('lang'),
          value: langs.contains(s.lang) ? s.lang : null,
          items: [
            for (final l in langs)
              DropdownMenuItem(
                value: l,
                child: ContentText(coachLangs[l] ?? l),
              ),
          ],
          onChanged: (l) => l == null ? null : s.setLang(l),
        ),
        const SizedBox(height: AppSpacing.sm),
        SqlEditor(controller: s.code),
        const SizedBox(height: AppSpacing.sm),
      ];
      final results = [
        RequestStatusLine(s.runs),
        if (report != null && report.held && s.note != null)
          noteCue(s.note!, key: const ValueKey('run-note')),
        if (report != null && !report.held)
          CoachRunView(report, key: ObjectKey(report)),
      ];
      // Phone: Run stays under the pages, above the keyboard.
      final list = isCompact(context)
          ? FitSplit(
              body: FitPages(
                padding: const EdgeInsets.all(AppSpacing.md),
                children: [...top, ...results],
              ),
              bar: Row(children: [run]),
            )
          : ListView(
              padding: const EdgeInsets.all(AppSpacing.md),
              keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
              children: [
                ...top,
                Row(children: [run]),
                ...results,
              ],
            );
      return WithSymbolBar(controller: s.code, show: touch, child: list);
    },
  );
}
