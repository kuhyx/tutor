/// Renders the tutor's tiny markdown (`session/markdown.dart`) as text
/// spans. Selectable, so a learner can copy a term.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/session/markdown.dart';

/// Markdown text.
class MarkdownText extends StatelessWidget {
  /// Creates the text.
  const new(this.text, {super.key});

  /// Source.
  final String text;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    List<InlineSpan> line(List<MdSpan> l) => mdInlineSpans(l, scheme);
    final blocks = parseMarkdown(text);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final b in blocks)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: b.kind == MdBlockKind.paragraph
                ? SelectableText.rich(
                    TextSpan(
                      children: [
                        for (final (i, l) in b.lines.indexed) ...[
                          if (i > 0) const TextSpan(text: '\n'),
                          ...line(l),
                        ],
                      ],
                    ),
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      for (final (i, l) in b.lines.indexed)
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            SizedBox(
                              width: AppSpacing.lg,
                              child: Text(
                                b.kind == MdBlockKind.numbered
                                    ? '${i + 1}.'
                                    : '•',
                              ),
                            ),
                            Expanded(
                              child: SelectableText.rich(
                                TextSpan(children: line(l)),
                              ),
                            ),
                          ],
                        ),
                    ],
                  ),
          ),
      ],
    );
  }
}

/// [spans] as text spans, styled as [MarkdownText] styles them.
List<InlineSpan> mdInlineSpans(List<MdSpan> spans, ColorScheme scheme) {
  final code = TextStyle(
    fontFamily: 'monospace',
    backgroundColor: scheme.surfaceContainerHighest,
  );
  return [
    for (final s in spans)
      TextSpan(
        text: s.text,
        style: switch (s.style) {
          MdStyle.plain => null,
          MdStyle.bold => const TextStyle(fontWeight: FontWeight.w600),
          MdStyle.em => const TextStyle(fontStyle: FontStyle.italic),
          MdStyle.code => code,
        },
      ),
  ];
}
