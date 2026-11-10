import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/coach/coach_models.dart';
import 'package:tutor/ui/fit_layouts.dart';
import 'package:tutor/ui/metrics_cap.dart';
import 'package:tutor/ui/sql/data_grid.dart';
import 'package:tutor/ui/sql/rich_md.dart';
import 'package:tutor/widgets/content_text.dart';

/// Rung, turn counter and gate try counter of `state`.
class StatusStrip extends StatelessWidget {
  /// Creates the strip.
  const new(this.state, {super.key});

  /// Session state.
  final CoachState state;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final gate = state.gate;
    Widget chip(String text, Key key, {bool bad = false}) => Padding(
      padding: const EdgeInsets.only(right: AppSpacing.sm),
      child: ContentText(
        text,
        key: key,
        style: sqlMono.copyWith(color: bad ? scheme.error : null),
      ),
    );
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.xs,
      ),
      child: Row(
        children: [
          if (state.rung != null) chip(state.rung!, const Key('rung')),
          if (state.budget > 0)
            chip(
              '${state.used}/${state.budget}',
              const Key('turns'),
              bad: state.over,
            ),
          if (!gate.open)
            chip('${gate.kind}: ${gate.tries}/${gate.max}', const Key('gate')),
        ],
      ),
    );
  }
}

/// The statement under a header that folds it.
class FoldingStatement extends StatelessWidget {
  /// Creates the header and body.
  const new({
    required this.title,
    required this.md,
    required this.open,
    required this.onToggle,
    super.key,
  });

  /// Problem title.
  final String title;

  /// Statement markdown.
  final String md;

  /// Whether the body shows.
  final bool open;

  /// Folds or unfolds.
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        InkWell(
          key: const ValueKey('statement-header'),
          onTap: onToggle,
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.md,
              vertical: AppSpacing.sm,
            ),
            child: Row(
              children: [
                const Icon(Icons.description_outlined, semanticLabel: 'Task'),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: ContentText(title, overflow: TextOverflow.ellipsis),
                ),
                Icon(open ? Icons.expand_less : Icons.expand_more),
              ],
            ),
          ),
        ),
        // Flexible: shares a short phone screen instead of overflowing.
        if (open)
          Flexible(
            child: CappedHeight(
              share: 0.3,
              child: fitScroll(
                context,
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.md,
                  0,
                  AppSpacing.md,
                  AppSpacing.sm,
                ),
                child: RichMd(md),
              ),
            ),
          ),
      ],
    );
  }
}

/// The snippet the last reply is about, kept above the answer box.
class PinnedSnippet extends StatelessWidget {
  /// Creates the pin.
  const new({required this.md, required this.onClose, super.key});

  /// Code fence or table markdown.
  final String md;

  /// Drops the pin.
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const ValueKey('pinned'),
      decoration: BoxDecoration(
        border: Border(
          top: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: CappedHeight(
              share: 0.22,
              child: fitScroll(
                context,
                padding: const EdgeInsets.all(AppSpacing.sm),
                child: RichMd(md),
              ),
            ),
          ),
          IconButton(
            key: const ValueKey('unpin'),
            onPressed: onClose,
            icon: const Icon(Icons.close, semanticLabel: 'Unpin'),
          ),
        ],
      ),
    );
  }
}

/// The worker's choices after a frustration stop; each sends its own text.
class ChoiceButtons extends StatelessWidget {
  /// Creates the row.
  const new({required this.choices, required this.onPick, super.key});

  /// Texts to send.
  final List<String> choices;

  /// Sends one.
  final ValueChanged<String> onPick;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
    child: Wrap(
      spacing: AppSpacing.sm,
      children: [
        for (final c in choices)
          FilledButton.tonal(
            key: ValueKey('choice-$c'),
            onPressed: () => onPick(c),
            child: ContentText(c),
          ),
      ],
    ),
  );
}
