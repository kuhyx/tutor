part of 'review_screen.dart';

// The app bar title and the card page (face + answer bar).
extension on _ReviewScreenState {
  // The mode's glyph, then the subject or module name (content) if any.
  Widget _title() {
    final name = widget.module?.title ?? widget.subjectTitle;
    final scoped = widget.module != null || widget.subject != null;
    return SpokenLabel(
      semanticLabel: _drill
          ? 'Drill'
          : widget.module != null
          ? 'Review: ${widget.module!.title}'
          : scoped
          ? 'Review: ${widget.subjectTitle ?? 'this subject'}'
          : 'Review',
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(_drill ? Icons.quiz_outlined : Icons.replay),
          if (!_drill && name != null) ...[
            const SizedBox(width: AppSpacing.sm),
            Flexible(child: ContentText(name, overflow: TextOverflow.ellipsis)),
          ],
        ],
      ),
    );
  }

  Widget _body(BuildContext context, ReviewSession run) {
    final item = run.current;
    final text = Theme.of(context).textTheme;
    if (item == null) return ReviewEnd(run, module: widget.module != null);
    final face = [
      Row(
        children: [
          Expanded(
            child: ContentText(item.subjectTitle, style: text.bodySmall),
          ),
          SpokenLabel(
            semanticLabel: '${run.left} left',
            child: GlyphStat(Icons.layers_outlined, '${run.left}'),
          ),
        ],
      ),
      const SizedBox(height: AppSpacing.md),
      CardFace(item.card, revealed: run.revealed),
    ];
    final bar = AnswerBar(run, onFlag: () => _flag(run));
    // Phone: the card pages, the answer bar stays under it on every page.
    if (isCompact(context)) {
      return FitSplit(
        body: PageList(children: face),
        bar: bar,
      );
    }
    return PageList(
      children: [
        ...face,
        const SizedBox(height: AppSpacing.md),
        bar,
      ],
    );
  }
}
