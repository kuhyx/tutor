part of 'editor_screen.dart';

// Row pieces of the card editor: a card's actions, Add card, a module's
// marks.
extension on _EditorScreenState {
  Widget _actions(SubjectData s, MapEntry<String, StudyCard> c) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      if (c.value.restorable)
        MergeSemantics(
          child: Semantics(
            hint: restoreTip(c.value),
            child: GlyphButton(
              icon: Icons.restore,
              semanticLabel: 'Restore',
              onPressed: () => _undo(RequestBody.cardRestore(s.id, c.key)),
            ),
          ),
        ),
      if (c.value.addedByTutor)
        GlyphButton(
          icon: Icons.remove_circle_outline,
          semanticLabel: 'Remove',
          onPressed: () => _undo(RequestBody.cardRemove(s.id, c.key)),
        ),
      GlyphButton(
        icon: Icons.flag_outlined,
        semanticLabel: 'Flag',
        onPressed: () => _flag(s, c.key, c.value),
      ),
    ],
  );

  Widget _addCard(SubjectData s, Module m) => Padding(
    padding: const EdgeInsets.all(AppSpacing.sm),
    child: Align(
      alignment: Alignment.centerRight,
      child: GlyphButton(
        icon: Icons.add,
        semanticLabel: 'Add card',
        onPressed: () => _edit(s, m),
      ),
    ),
  );

  // Cards, mark and done / recalled / due as glyph + number marks; the old
  // line (and the words' explanation) is the spoken label.
  Widget _moduleSub(SubjectData s, Module m, SubjectProgress? progress) {
    final mark = moduleMark(m, progress?.review[m.id]);
    final tally = progress?.modules[m.id];
    final counted = (tally?.cards ?? 0) > 0;
    final n = s.cardsOf(m.id).length;
    return SpokenLabel(
      semanticLabel: [
        _cards(n),
        mark.name,
        if (counted) tally!.doneText,
        ?badgeHelp(mark.name),
        tallyHelp,
      ].join(' · '),
      child: Wrap(
        spacing: AppSpacing.md,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          GlyphStat(Icons.style_outlined, '$n'),
          Icon(moduleMarkIcon(mark), color: moduleMarkColor(context, mark)),
          if (counted) TallyRow(tally!),
        ],
      ),
    );
  }
}
