/// The module gate held by cards read without Claude (mockup F5, spec Q11):
/// one row per card, its front beside the "unchecked" glyph, and a Start
/// that opens a Claude session on the subject. That session checks those
/// cards first (`SubjectSource.pick`); a review never passes them, so the
/// gate flow opens this instead of a review and resends nothing.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/session/session_screen.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// The cards' list screen.
class UncheckedGateScreen extends StatelessWidget {
  /// Creates the screen for [subject]'s card [fronts] (id -> front).
  const new({
    required this.services,
    required this.subject,
    required this.fronts,
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// Subject id.
  final String subject;

  /// Card id -> its front, in the worker's order.
  final Map<String, String> fronts;

  // The check: a Claude session on the subject, the gate flow left behind
  // (Back then lands on Home, not on the refused Session).
  void _check(BuildContext context) => Navigator.of(context).pushAndRemoveUntil(
    MaterialPageRoute<void>(
      builder: (_) =>
          SessionScreen(services: services, subject: subject, resume: true),
    ),
    (route) => route.isFirst,
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      actions: const [
        Padding(
          padding: EdgeInsets.symmetric(horizontal: AppSpacing.md),
          child: SpokenLabel(
            semanticLabel: 'Waiting for Claude’s check',
            child: Icon(Icons.pending_actions, color: AppPalette.warning),
          ),
        ),
      ],
    ),
    body: PageList(
      children: [
        for (final MapEntry(key: id, value: front) in fronts.entries)
          Card(
            key: ValueKey('unchecked-$id'),
            child: ListTile(
              leading: const UncheckedGlyph(),
              title: ContentText(front),
            ),
          ),
        const SizedBox(height: AppSpacing.xl),
        Center(
          child: GlyphButton(
            icon: Icons.play_arrow,
            semanticLabel: 'Check with Claude',
            tooltip: (l) => l.tooltip_check,
            filled: true,
            onPressed: () => _check(context),
          ),
        ),
      ],
    ),
  );
}

/// A card read without Claude and not checked yet: the glyph, its one
/// tooltip word, and the spoken label.
class UncheckedGlyph extends StatelessWidget {
  /// Creates the glyph.
  const new({super.key});

  @override
  Widget build(BuildContext context) => Tooltip(
    message: AppLocalizations.of(context).tooltip_unchecked,
    excludeFromSemantics: true, // the spoken label says it
    child: SpokenLabel(
      semanticLabel: 'Not checked by Claude yet',
      child: Icon(
        Icons.pending_actions,
        color: Theme.of(context).colorScheme.primary,
      ),
    ),
  );
}
