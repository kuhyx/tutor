part of 'drill_view.dart';

// The graded answer, the day's credit and the Anki sync line.
extension on _DrillViewState {
  List<Widget> _graded(TextTheme text, DrillAnswer a) => [
    SpokenLabel(
      semanticLabel: a.correct
          ? 'Correct${a.minuteCredited ? ' · +1 min credited' : ''}'
          : 'Not quite',
      liveRegion: true,
      child: Row(
        children: [
          Icon(
            a.correct ? Icons.check_circle : Icons.cancel_outlined,
            color: a.correct ? AppPalette.success : AppPalette.danger,
          ),
          if (a.correct && a.minuteCredited) ...[
            const SizedBox(width: AppSpacing.sm),
            const GlyphStat(Icons.timer_outlined, '+1'),
          ],
        ],
      ),
    ),
    const SizedBox(height: AppSpacing.xs),
    ContentText(a.back, style: text.bodyLarge),
    const SizedBox(height: AppSpacing.sm),
    ContentText(
      '"${a.excerpt}"',
      style: text.bodyMedium?.copyWith(fontStyle: FontStyle.italic),
    ),
    const SizedBox(height: AppSpacing.xs),
    LinkText(hostOf(a.source), a.source),
  ];

  // One line: the day's credited minutes; on Android the Anki sync beside it.
  Widget _header(DrillToday? today) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(
        children: [
          Expanded(
            child: today == null
                ? const SizedBox.shrink()
                : Align(
                    alignment: Alignment.centerLeft,
                    child: SpokenLabel(
                      semanticLabel: 'Today: ${today.creditedMin} min credited',
                      child: GlyphStat(
                        Icons.timer_outlined,
                        '${today.creditedMin}',
                        size: AppTextSize.label,
                      ),
                    ),
                  ),
          ),
          if (_anki.launcher.supported)
            GlyphButton(
              icon: Icons.sync,
              semanticLabel: 'Sync Anki & credit',
              onPressed: _anki.running ? null : () => unawaited(_anki.run()),
            ),
        ],
      ),
      if (_anki.message != null) _ankiCue(),
    ],
  );

  // The sync's outcome as a cue; "+3 min" shows as the number.
  Widget _ankiCue() {
    final (kind, icon) = switch (_anki.outcome) {
      AnkiOutcome.syncing || null => (CueKind.pending, null),
      AnkiOutcome.gained => (CueKind.ok, Icons.timer_outlined),
      AnkiOutcome.none => (CueKind.blocked, Icons.sync_problem),
      AnkiOutcome.notStarted => (CueKind.error, Icons.sync_disabled),
    };
    return Row(
      children: [
        CueChip(kind: kind, icon: icon, semanticLabel: _anki.message!),
        if (_anki.outcome == AnkiOutcome.gained) ...[
          const SizedBox(width: AppSpacing.sm),
          GlyphStat(Icons.add, '${_anki.gained}', size: AppTextSize.label),
        ],
      ],
    );
  }
}
