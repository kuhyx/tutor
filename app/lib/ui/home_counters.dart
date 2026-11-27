/// Home's Today counters as glyph + number (no words): credited/target
/// minutes, active minutes, new cards, the bank, and what kuhy earned
/// himself today (own minutes, LeetCode minutes; DOCS-contract-carry.md
/// "Stats").
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/spoken_label.dart';
import 'package:tutor/widgets/text_free_theme.dart';

/// Today's counters; own and LeetCode minutes only when > 0.
class HomeCounters extends StatelessWidget {
  /// Creates the counters for [today].
  const new(this.today, {super.key});

  /// `stats.today`.
  final Today today;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final l10n = Localizations.of<AppLocalizations>(context, AppLocalizations);
    final banked = today.banked ?? 0;
    final prepaid = today.prepaid ?? 0;
    final active = today.activeMinutes;
    final own = today.ownMinutes;
    final lc = today.lcMinutes;
    // One hover word naming the glyph; the spoken label already says it.
    Widget hover(String? word, Widget child) => word == null
        ? child
        : approvedTooltip(
            message: word,
            excludeFromSemantics: true,
            child: child,
          );
    return Wrap(
      spacing: AppSpacing.md,
      runSpacing: AppSpacing.xs,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        SpokenLabel(
          semanticLabel:
              'Credited ${today.creditedMinutes}/${today.target} min',
          child: GlyphStat(
            Icons.verified_outlined,
            '${today.creditedMinutes}/${today.target}',
            color: scheme.primary,
          ),
        ),
        if (active != null)
          SpokenLabel(
            semanticLabel: '$active min active',
            child: GlyphStat(Icons.timer_outlined, '$active'),
          ),
        SpokenLabel(
          semanticLabel: 'new cards ${today.newCards}',
          child: GlyphStat(Icons.add_card, '${today.newCards}'),
        ),
        if (banked > 0 || prepaid > 0)
          SpokenLabel(
            semanticLabel: 'Banked $banked min · prepaid $prepaid',
            child: GlyphStat(Icons.savings_outlined, '$banked · $prepaid'),
          ),
        if (own > 0)
          hover(
            l10n?.tooltip_own,
            SpokenLabel(
              semanticLabel: '$own min own work today',
              child: GlyphStat(
                Icons.person_outline,
                '$own',
                color: AppPalette.success,
              ),
            ),
          ),
        if (lc > 0)
          hover(
            l10n?.tooltip_leetcode,
            SpokenLabel(
              semanticLabel: '$lc min LeetCode today',
              child: GlyphStat(Icons.code, '$lc', color: scheme.secondary),
            ),
          ),
      ],
    );
  }
}
