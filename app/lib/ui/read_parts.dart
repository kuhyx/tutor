/// Pieces of read mode: the progress dots, the card (front, or both sides
/// with the source quote and link) and the pinned rate bar.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/drill/read_models.dart';
import 'package:tutor/editor/card_rules.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/spoken_label.dart';
import 'package:tutor/widgets/text_free_theme.dart';

/// Dots in one cycle of [ReadDots].
const kReadDots = 5;

/// Cards read this run as a row of dots: each card lights one more, a full
/// row starts over with the next card.
class ReadDots extends StatelessWidget {
  /// Creates the row.
  const new(this.rated, {super.key});

  /// Cards rated this run.
  final int rated;

  @override
  Widget build(BuildContext context) {
    final on = rated == 0 ? 0 : (rated - 1) % kReadDots + 1;
    final off = Theme.of(context).colorScheme.outlineVariant;
    return SpokenLabel(
      semanticLabel: 'Read: $rated',
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          for (var i = 0; i < kReadDots; i++)
            Container(
              width: AppSpacing.sm,
              height: AppSpacing.sm,
              margin: const EdgeInsets.symmetric(horizontal: AppSpacing.xs),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: i < on ? AppPalette.accent : off,
              ),
            ),
        ],
      ),
    );
  }
}

/// The card: its front and a flip glyph; once [flipped] also the back, the
/// excerpt as an accent-ruled italic quote and the source link.
class ReadCardView extends StatelessWidget {
  /// Creates the card; [onFlip] null while a request is out.
  const new(
    this.card, {
    required this.flipped,
    required this.onFlip,
    super.key,
  });

  /// The card shown.
  final ReadCard card;

  /// Whether the back shows.
  final bool flipped;

  /// Shows the back (a tap anywhere on the front).
  final VoidCallback? onFlip;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final body = Padding(
      padding: const EdgeInsets.all(AppSpacing.md + AppSpacing.xs),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ContentText(card.front, style: text.titleLarge),
          if (!flipped) ...[
            const SizedBox(height: AppSpacing.lg),
            Center(
              child: GlyphButton(
                icon: Icons.flip,
                semanticLabel: 'Flip card',
                tooltip: (l) => l.tooltip_reveal,
                size: 40,
                target: 64,
                tint: Theme.of(context).colorScheme.onSurfaceVariant,
                onPressed: onFlip,
              ),
            ),
          ] else
            ..._back(context, text),
        ],
      ),
    );
    return Card(
      clipBehavior: Clip.antiAlias,
      child: flipped ? body : InkWell(onTap: onFlip, child: body),
    );
  }

  List<Widget> _back(BuildContext context, TextTheme text) {
    final muted = Theme.of(context).colorScheme.onSurfaceVariant;
    return [
      const Divider(height: AppSpacing.xl),
      ContentText(card.back, style: text.bodyLarge),
      const SizedBox(height: AppSpacing.md),
      Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
        decoration: const BoxDecoration(
          border: Border(left: BorderSide(color: AppPalette.accent, width: 3)),
        ),
        child: ContentText(
          '“${card.excerpt}”',
          style: text.bodyMedium?.copyWith(
            fontStyle: FontStyle.italic,
            color: muted,
          ),
        ),
      ),
      const SizedBox(height: AppSpacing.sm),
      Row(
        children: [
          Icon(Icons.link, size: 16, color: muted),
          const SizedBox(width: AppSpacing.sm),
          Flexible(child: LinkText(hostOf(card.source), card.source)),
        ],
      ),
    ];
  }
}

/// The two rate buttons pinned under the page: again (red) and got it
/// (green); [onRate] null while a request is out.
class ReadRateBar extends StatelessWidget {
  /// Creates the bar.
  const new({required this.onRate, super.key});

  /// Rates the open card.
  final void Function(ReadRating rating)? onRate;

  @override
  Widget build(BuildContext context) => SafeArea(
    top: false,
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: kPageMaxWidth),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.md,
          AppSpacing.xs,
          AppSpacing.md,
          AppSpacing.md,
        ),
        child: Row(
          children: [
            _button(context, ReadRating.again),
            const SizedBox(width: AppSpacing.md),
            _button(context, ReadRating.gotIt),
          ],
        ),
      ),
    ),
  );

  Widget _button(BuildContext context, ReadRating rating) {
    final (icon, tint, label) = switch (rating) {
      ReadRating.again => (Icons.replay, AppPalette.danger, 'Again'),
      ReadRating.gotIt => (
        Icons.check_circle_outline,
        AppPalette.success,
        'Got it',
      ),
    };
    final rate = onRate;
    final tap = rate == null ? null : () => rate(rating);
    final l10n = Localizations.of<AppLocalizations>(context, AppLocalizations);
    Widget button = SpokenLabel(
      semanticLabel: label,
      button: true,
      enabled: tap != null,
      onTap: tap,
      child: FilledButton(
        onPressed: tap,
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(72),
          backgroundColor: tint.withValues(alpha: 0.18),
          foregroundColor: tint,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppRadius.lg),
          ),
        ),
        child: Icon(icon, size: 36),
      ),
    );
    if (l10n != null) {
      button = approvedTooltip(
        message: rating == ReadRating.again
            ? l10n.tooltip_again
            : l10n.tooltip_known,
        excludeFromSemantics: true,
        child: button,
      );
    }
    return Expanded(child: button);
  }
}
