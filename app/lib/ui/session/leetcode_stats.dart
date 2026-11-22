/// The LeetCode stats of a theory lesson, in the Session's top bar: minutes
/// towards the next credit, credits minted today, solves still owed, cards
/// taught in the unit (kuhy, 2026-11-22). Glyph + number; a count the
/// server could not check paints `?`, never 0. The wording is spoken only;
/// each glyph carries a one-word tooltip.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/leetcode.dart';
import 'package:tutor/session/leetcode_label.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// The bar's pencil: the unit replaces the subject as the title.
const IconData kUnitIcon = Icons.edit_outlined;

String _q(int? n) => n == null ? '?' : '$n';

/// The four stats of [meta].
class LeetcodeStats extends StatelessWidget {
  /// Creates the row.
  const new({required this.meta, super.key});

  /// The lesson's accounting.
  final LeetcodeMeta meta;

  @override
  Widget build(BuildContext context) {
    final lines = leetcodeLines(meta);
    final into = meta.into;
    final per = meta.perCredit;
    final ratio = into == null && per == null ? '?' : '${_q(into)}/${_q(per)}';
    return Wrap(
      spacing: AppSpacing.md,
      runSpacing: AppSpacing.xs,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        _Glyph(
          tip: 'Minutes',
          label: lines.minutes,
          child: meta.full
              ? const Icon(
                  Icons.timer_off_outlined,
                  size: AppTextSize.subtitle + 2,
                  color: AppPalette.warning,
                )
              : GlyphStat(
                  Icons.timer_outlined,
                  ratio,
                  size: AppTextSize.subtitle,
                ),
        ),
        _Glyph(
          tip: 'Credits',
          label: lines.credits,
          child: GlyphStat(
            Icons.diamond_outlined,
            _q(meta.credits),
            size: AppTextSize.subtitle,
          ),
        ),
        _Glyph(
          tip: 'Owed',
          label: lines.needed,
          child: GlyphStat(
            Icons.circle_outlined,
            _q(meta.needed),
            size: AppTextSize.subtitle,
          ),
        ),
        _Glyph(
          tip: 'Cards',
          label: lines.cards,
          child: GlyphStat(
            Icons.style_outlined,
            '${meta.taught}/${meta.total}',
            size: AppTextSize.subtitle,
          ),
        ),
      ],
    );
  }
}

class _Glyph extends StatelessWidget {
  const new({required this.tip, required this.label, required this.child});

  final String tip;
  final String label;
  final Widget child;

  @override
  Widget build(BuildContext context) => Tooltip(
    message: tip,
    excludeFromSemantics: true, // the spoken line says it
    child: SpokenLabel(semanticLabel: label, child: child),
  );
}
