/// The tutor's tiny markdown, ported from `static/app.js` (`markdown`,
/// `inline`): paragraphs split on blank lines, a block whose every line
/// starts with `- `/`* `/`1. ` is a list, and inline `**bold**`, `*em*`,
/// `` `code` ``.
///
/// There is no HTML path at all (DOCS-contract §10): every span is plain
/// text with a style, so model output can never become markup or a link.
library;

import 'package:flutter/foundation.dart' show immutable;

/// Inline style of a [MdSpan].
enum MdStyle {
  /// Plain text.
  plain,

  /// `**bold**`.
  bold,

  /// `*em*`.
  em,

  /// `` `code` ``.
  code,
}

/// A run of text in one style.
@immutable
class MdSpan {
  /// Creates the span.
  const new(this.text, [this.style = MdStyle.plain]);

  /// The text, markers removed.
  final String text;

  /// Its style.
  final MdStyle style;

  @override
  bool operator ==(Object other) =>
      other is MdSpan && other.text == text && other.style == style;

  @override
  int get hashCode => Object.hash(text, style);

  @override
  String toString() => '${style.name}($text)';
}

/// Block kind.
enum MdBlockKind {
  /// A paragraph; each line is a hard line break.
  paragraph,

  /// A bulleted list; each line is an item.
  bullets,

  /// A numbered list; each line is an item.
  numbered,
}

/// One block: its lines (paragraph lines or list items) as spans.
class MdBlock {
  /// Creates the block.
  const new(this.kind, this.lines);

  /// Kind.
  final MdBlockKind kind;

  /// Lines, each a list of spans.
  final List<List<MdSpan>> lines;
}

final _blankLines = RegExp(r'\n{2,}');
final _item = RegExp(r'^\s*([-*]|\d+\.)\s+');
final _numbered = RegExp(r'^\s*\d+\.');
final _inline = RegExp(r'(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)');

/// Parses [text] into blocks.
List<MdBlock> parseMarkdown(String text) => [
  for (final block in text.split(_blankLines))
    if (block.trim().isNotEmpty) _block(block),
];

MdBlock _block(String block) {
  final lines = block.split('\n');
  if (lines.every(_item.hasMatch)) {
    return MdBlock(
      _numbered.hasMatch(lines.first)
          ? MdBlockKind.numbered
          : MdBlockKind.bullets,
      [for (final l in lines) parseInline(l.replaceFirst(_item, ''))],
    );
  }
  return MdBlock(MdBlockKind.paragraph, [
    for (final l in lines) parseInline(l),
  ]);
}

/// Splits one line into styled spans.
List<MdSpan> parseInline(String line) {
  final out = <MdSpan>[];
  var at = 0;
  for (final m in _inline.allMatches(line)) {
    if (m.start > at) out.add(MdSpan(line.substring(at, m.start)));
    out.add(_styled(m.group(0)!));
    at = m.end;
  }
  if (at < line.length) out.add(MdSpan(line.substring(at)));
  return out;
}

MdSpan _styled(String part) {
  if (part.startsWith('**')) {
    return MdSpan(part.substring(2, part.length - 2), MdStyle.bold);
  }
  if (part.startsWith('`')) {
    return MdSpan(part.substring(1, part.length - 1), MdStyle.code);
  }
  // `*x*`: the regex guarantees at least one char between the stars.
  return MdSpan(part.substring(1, part.length - 1), MdStyle.em);
}
