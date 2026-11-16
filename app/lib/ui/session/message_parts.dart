/// The small parts of a chat message: the check result, a read-only
/// question and the filled banner.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// The comprehension-check result with the tutor's feedback.
class CheckResultBanner extends StatelessWidget {
  /// Creates the banner.
  const new(this.result, {super.key});

  /// The `check_result` record.
  final Map<String, dynamic> result;

  @override
  Widget build(BuildContext context) {
    final passed = result['passed'] == true;
    final feedback = result['feedback'];
    return MessageBanner(
      icon: passed ? Icons.fact_check : Icons.replay,
      spoken: 'Check ${passed ? 'passed' : 'not yet'}',
      // The tutor's feedback on the answer: content.
      feedback: feedback is String ? feedback : null,
      ok: passed,
    );
  }
}

/// A read-only question (the composer's boxes are not showing it).
class AskedQuestion extends StatelessWidget {
  /// Creates the question.
  const new(this.asked, {super.key});

  /// The question.
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
        Row(
          children: [
            SpokenLabel(
              semanticLabel: asked.heading,
              child: Text(
                asked.label,
                style: Theme.of(context).textTheme.labelMedium,
              ),
            ),
            if (asked.check)
              const Icon(Icons.fact_check_outlined, size: AppTextSize.label),
          ],
        ),
        ContentText(asked.text),
      ],
    ),
  );
}

/// A filled banner: glyph (spoken label) and optional feedback text.
class MessageBanner extends StatelessWidget {
  /// Creates the banner.
  const new({
    required this.icon,
    required this.spoken,
    required this.ok,
    this.feedback,
    super.key,
  });

  /// The glyph.
  final IconData icon;

  /// What a screen reader says.
  final String spoken;

  /// Green (true) or amber.
  final bool ok;

  /// The tutor's words, if any (content).
  final String? feedback;

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    margin: const EdgeInsets.only(top: AppSpacing.sm),
    padding: const EdgeInsets.all(AppSpacing.sm),
    decoration: BoxDecoration(
      color: ok ? AppPalette.success : AppPalette.warning,
      borderRadius: BorderRadius.circular(AppRadius.sm),
    ),
    child: Row(
      children: [
        SpokenLabel(
          semanticLabel: spoken,
          child: Icon(icon, color: AppPalette.onFill),
        ),
        if (feedback != null && feedback!.isNotEmpty) ...[
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: ContentText(
              feedback!,
              style: const TextStyle(color: AppPalette.onFill),
            ),
          ),
        ],
      ],
    ),
  );
}
