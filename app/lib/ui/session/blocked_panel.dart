/// A blocking result (`daily_new_cap`, `locked`, `no_card_left`) as a call
/// to action, never an error: one short line on why, a primary button that
/// fixes it at once, and "Review this subject (N due)" when cards wait.
/// No red, and never the worker's raw text (kuhy, 2026-10-17: a red "Ten
/// new cards today already" with no way on to the next module).
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/blocked.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/spoken_label.dart';

typedef _Act = Future<void> Function(BuildContext);

/// The call to action for [blocked].
class BlockedPanel extends StatelessWidget {
  /// Creates the panel; [text] is the line, [subject] the screen's subject
  /// (a hint when the payload names none), [lastBody] the request that was
  /// blocked (Learn more anyway re-sends it with `lift_cap`).
  const new({
    required this.services,
    required this.blocked,
    required this.text,
    required this.onRun,
    this.subject,
    this.lastBody,
    super.key,
  });

  /// Services (the catalog, and Review).
  final TutorServices services;

  /// The block.
  final Blocked blocked;

  /// Why, in one line.
  final String text;

  /// The screen's subject.
  final String? subject;

  /// The blocked request.
  final RequestBody? lastBody;

  /// Runs a request on the screen's runner.
  final Future<RelayStatus> Function(RequestBody body) onRun;

  @override
  Widget build(BuildContext context) {
    final b = blocked;
    final due = b.dueInSubject ?? 0;
    final primary = switch (b) {
      Blocked(code: dailyNewCap) => (
        'Learn more anyway',
        Icons.lock_open,
        0,
        _liftCap,
      ),
      Blocked(reviewsModule: true) => (
        'Review ${b.moduleTitle ?? 'this module'}',
        Icons.menu_book_outlined,
        0,
        _reviewModule,
      ),
      _ => null,
    };
    final review = due > 0
        ? ('Review this subject ($due due)', Icons.style, due, _reviewSubject)
        : null;
    // The first action is the prominent one (right); a second is plain.
    final actions = <(String, IconData, int, _Act)>[?primary, ?review];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Why: the call-to-action glyph on an amber chip, not a sentence.
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: CueChip(
                kind: CueKind.blocked,
                icon: _whyIcon(b),
                semanticLabel: text,
              ),
            ),
            if (actions.isNotEmpty) const SizedBox(height: AppSpacing.md),
            if (actions.isNotEmpty)
              Wrap(
                alignment: WrapAlignment.end,
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.sm,
                children: [
                  for (final (label, icon, n, act) in actions.skip(1))
                    GlyphButton(
                      icon: icon,
                      semanticLabel: label,
                      count: n > 0 ? n : null,
                      onPressed: () => unawaited(act(context)),
                    ),
                  GlyphButton(
                    icon: actions.first.$2,
                    semanticLabel: actions.first.$1,
                    count: actions.first.$3 > 0 ? actions.first.$3 : null,
                    filled: true,
                    onPressed: () => unawaited(actions.first.$4(context)),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  static IconData _whyIcon(Blocked b) => switch (b.code) {
    dailyNewCap => Icons.speed,
    lockedCode => Icons.lock_outline,
    _ => Icons.inbox_outlined,
  };

  // The blocked `session_start` again with `lift_cap`; anything else (Next
  // card) starts the subject's next card with the cap lifted.
  Future<void> _liftCap(BuildContext context) async {
    final again = lastBody?.liftingCap();
    if (again != null) {
      await onRun(again);
      return;
    }
    final id = blocked.subjectId(
      await services.catalog.cached(),
      hint: subject,
    );
    await onRun(RequestBody.sessionStart(subject: id, liftCap: true));
  }

  // The payload names the module but not always the subject id: the cached
  // plan that holds the module does (the screen's subject first).
  Future<void> _reviewModule(BuildContext context) async {
    final ref = blocked.moduleRef(
      await services.catalog.cached(),
      hint: subject,
    );
    if (ref != null && context.mounted) {
      await openReview(context, services, module: ref);
    }
  }

  // Only this subject's due cards, never another subject's.
  Future<void> _reviewSubject(BuildContext context) async {
    final subjects = await services.catalog.cached();
    final id = blocked.subjectId(subjects, hint: subject);
    if (id == null || !context.mounted) return;
    await openReview(
      context,
      services,
      subject: id,
      subjectTitle: blocked.subjectTitle ?? subjects[id]?.meta.title,
    );
  }
}
