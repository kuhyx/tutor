/// One chat message, as `static/app.js` renderMessage draws it: tutor
/// (tag, ⚑ Report on live messages, markdown, pictures, diagrams, check
/// result, read-only questions, card edit notices, Card done), learner,
/// or a card divider.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/progress/terms.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/ui/session/md_text.dart';
import 'package:tutor/ui/session/media.dart';

/// A message bubble.
class MessageTile extends StatelessWidget {
  /// Creates the tile. [onReport] null = read-only (past session);
  /// [questionsAsBoxes] = its questions are live answer boxes below.
  const new({
    required this.message,
    this.onReport,
    this.questionsAsBoxes = false,
    this.pending = false,
    super.key,
  });

  /// The message.
  final Message message;

  /// Reports a problem with this message.
  final VoidCallback? onReport;

  /// Leave the questions out (they are in the composer).
  final bool questionsAsBoxes;

  /// A learner text not yet answered (DOCS-contract §6 `busy.text`).
  final bool pending;

  @override
  Widget build(BuildContext context) {
    final m = message;
    final scheme = Theme.of(context).colorScheme;
    final text = Theme.of(context).textTheme;
    if (m.role == 'card') {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
        child: Row(
          children: [
            const Expanded(child: Divider()),
            Flexible(
              flex: 4,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
                child: Text(
                  'Next card: ${m.text}',
                  style: text.labelLarge,
                  textAlign: TextAlign.center,
                ),
              ),
            ),
            const Expanded(child: Divider()),
          ],
        ),
      );
    }
    final tutor = m.role == 'tutor';
    return Align(
      alignment: tutor ? Alignment.centerLeft : Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.only(bottom: AppSpacing.md),
        padding: const EdgeInsets.all(AppSpacing.md),
        constraints: const BoxConstraints(maxWidth: 680),
        decoration: BoxDecoration(
          color: tutor
              ? scheme.surfaceContainerLow
              : scheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(AppRadius.md),
          border: pending ? Border.all(color: scheme.outline) : null,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (tutor)
              Row(
                children: [
                  Expanded(
                    child: Text(
                      m.lowEffort
                          ? 'Tutor (last reply was low effort)'
                          : 'Tutor',
                      style: text.labelMedium,
                    ),
                  ),
                  if (onReport != null)
                    TextButton(
                      onPressed: onReport,
                      child: const Text('⚑ Report'),
                    ),
                ],
              )
            else if (pending)
              Text('You (sending...)', style: text.labelMedium),
            MarkdownText(m.text),
            for (final img in m.images) CommonsFigure(img),
            for (final d in m.diagrams) DiagramView(d),
            if (m.checkResult case final r?) _CheckResult(r),
            if (!questionsAsBoxes)
              for (final a in askedOf(m)) _Question(a),
            if (m.masteredNew.isNotEmpty)
              Tooltip(
                message: knownHelp,
                child: Text(
                  'Known: ${m.masteredNew.join(', ')}',
                  style: text.bodySmall,
                ),
              ),
            for (final n in m.notices) Text(n, style: text.labelMedium),
            if (m.cardDone) const _Banner('Card done ✓', ok: true),
          ],
        ),
      ),
    );
  }
}

class _CheckResult extends StatelessWidget {
  const new(this.result);

  final Map<String, dynamic> result;

  @override
  Widget build(BuildContext context) {
    final passed = result['passed'] == true;
    final feedback = result['feedback'];
    return _Banner(
      'Check ${passed ? 'passed' : 'not yet'}: '
      '${feedback is String ? feedback : ''}',
      ok: passed,
    );
  }
}

class _Question extends StatelessWidget {
  const new(this.asked);

  final Asked asked;

  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(top: AppSpacing.sm),
    padding: const EdgeInsets.only(left: AppSpacing.sm),
    decoration: BoxDecoration(
      border: Border(
        left: BorderSide(
          color: Theme.of(context).colorScheme.primary,
          width: 3,
        ),
      ),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(asked.heading, style: Theme.of(context).textTheme.labelMedium),
        Text(asked.text),
      ],
    ),
  );
}

class _Banner extends StatelessWidget {
  const new(this.text, {required this.ok});

  final String text;
  final bool ok;

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    margin: const EdgeInsets.only(top: AppSpacing.sm),
    padding: const EdgeInsets.all(AppSpacing.sm),
    decoration: BoxDecoration(
      color: ok ? AppPalette.success : AppPalette.warning,
      borderRadius: BorderRadius.circular(AppRadius.sm),
    ),
    child: Text(text, style: const TextStyle(color: AppPalette.onFill)),
  );
}
