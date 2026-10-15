/// Pieces of the drill: option buttons, the Claude-out banner, the retry.
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// Thumb-sized: 56 high, horizontal padding twice the vertical.
final ButtonStyle drillButton = FilledButton.styleFrom(
  minimumSize: const Size.fromHeight(56),
  padding: const EdgeInsets.symmetric(
    horizontal: AppSpacing.lg,
    vertical: AppSpacing.sm + AppSpacing.xs,
  ),
);

/// One answer option; [mark] true = the right one, false = the wrong pick.
class DrillOption extends StatelessWidget {
  /// Creates the option.
  const new(this.label, {required this.mark, required this.onTap, super.key});

  /// Option text.
  final String label;

  /// True = the right one, false = the wrong pick, null = none.
  final bool? mark;

  /// Pick; null once graded or while a request is out.
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final fill = switch (mark) {
      true => AppPalette.success,
      false => AppPalette.danger,
      null => null,
    };
    final body = Row(
      children: [
        Expanded(child: Text(label, style: const TextStyle(fontSize: 16))),
        if (mark != null)
          Icon(mark! ? Icons.check : Icons.close, color: AppPalette.onFill),
      ],
    );
    final style =
        (fill == null ? OutlinedButton.styleFrom : FilledButton.styleFrom)(
          minimumSize: const Size.fromHeight(56),
          alignment: Alignment.centerLeft,
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.lg,
            vertical: AppSpacing.sm + AppSpacing.xs,
          ),
          disabledBackgroundColor: fill,
          disabledForegroundColor: fill == null ? null : AppPalette.onFill,
        );
    return fill == null
        ? OutlinedButton(onPressed: onTap, style: style, child: body)
        : FilledButton(onPressed: null, style: style, child: body);
  }
}

/// The one-line "Claude limit — back at HH:MM" strip.
class DrillBanner extends StatelessWidget {
  /// Creates the banner.
  const new(this.text, {super.key});

  /// Banner text.
  final String text;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(
      horizontal: AppSpacing.md,
      vertical: AppSpacing.sm,
    ),
    margin: const EdgeInsets.only(bottom: AppSpacing.sm),
    decoration: BoxDecoration(
      color: AppPalette.warning,
      borderRadius: BorderRadius.circular(AppRadius.md),
    ),
    child: Text(
      text,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
      style: const TextStyle(color: AppPalette.onFill, fontSize: 14),
    ),
  );
}

/// A failed request: its text and Retry.
class DrillFailed extends StatelessWidget {
  /// Creates the block.
  const new(this.error, this.onRetry, {super.key});

  /// Error text.
  final String error;

  /// Sends the failed request again.
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Text(error),
      const SizedBox(height: AppSpacing.sm),
      FilledButton(
        style: drillButton,
        onPressed: () => unawaited(onRetry()),
        child: const Text('Retry'),
      ),
    ],
  );
}
