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

  TextSpan _span(MdSpan s, TextStyle code) => TextSpan(
    text: s.text,
    style: switch (s.style) {
      MdStyle.plain => null,
      MdStyle.bold => const TextStyle(fontWeight: FontWeight.w600),
      MdStyle.em => const TextStyle(fontStyle: FontStyle.italic),
      MdStyle.code => code,
    },
  );

  List<InlineSpan> _line(List<MdSpan> spans, TextStyle code) => [
    for (final s in spans) _span(s, code),
  ];

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final code = TextStyle(
      fontFamily: 'monospace',
      backgroundColor: scheme.surfaceContainerHighest,
    );
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
                          ..._line(l, code),
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
                                TextSpan(children: _line(l, code)),
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
