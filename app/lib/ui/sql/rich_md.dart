/// Markdown with the two blocks the tiny parser lacks: fenced code and
/// pipe tables.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/ui/session/md_text.dart';
import 'package:tutor/ui/sql/data_grid.dart';
import 'package:tutor/widgets/content_text.dart';

final _fence = RegExp(r'```[a-zA-Z]*\n?(.*?)```', dotAll: true);
final _rule = RegExp(r'^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$');

/// A selectable monospace block.
class CodeBlock extends StatelessWidget {
  /// Creates the block.
  const new(this.code, {super.key});

  /// The text.
  final String code;

  @override
  Widget build(BuildContext context) => ContentScope(
    child: DecoratedBox(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.sm),
        // Wraps: a query clipped at the screen edge cannot be answered.
        child: SelectableText(code.trimRight(), style: sqlMono),
      ),
    ),
  );
}

/// [text] as paragraphs, code blocks and tables.
class RichMd extends StatelessWidget {
  /// Creates the view.
  const new(this.text, {super.key});

  /// Markdown source.
  final String text;

  @override
  Widget build(BuildContext context) {
    const gap = SizedBox(height: AppSpacing.sm);
    final parts = <Widget>[];
    var at = 0;
    for (final m in _fence.allMatches(text)) {
      parts
        ..addAll(_prose(text.substring(at, m.start)))
        ..add(CodeBlock(m.group(1) ?? ''));
      at = m.end;
    }
    parts.addAll(_prose(text.substring(at)));
    return ContentScope(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final p in parts) ...[p, gap],
        ],
      ),
    );
  }
}

List<String> _cells(String line) {
  var t = line.trim();
  if (t.startsWith('|')) t = t.substring(1);
  if (t.endsWith('|')) t = t.substring(0, t.length - 1);
  return [for (final c in t.split('|')) c.trim()];
}

final _item = RegExp(r'^\s*([-*>]|\d+\.|#)\s');

/// Joins source lines hard-wrapped at 72 columns: a line continues the one
/// above unless it is blank or opens a list item or heading.
String _unwrap(List<String> lines) {
  final out = StringBuffer();
  for (var i = 0; i < lines.length; i++) {
    final line = lines[i];
    final joins =
        i > 0 &&
        line.trim().isNotEmpty &&
        lines[i - 1].trim().isNotEmpty &&
        !_item.hasMatch(line);
    if (i > 0) out.write(joins ? ' ' : '\n');
    out.write(joins ? line.trim() : line);
  }
  return out.toString();
}

List<Widget> _prose(String text) {
  final lines = text.split('\n');
  final out = <Widget>[];
  final plain = <String>[];
  void flush() {
    final md = _unwrap(plain).trim();
    if (md.isNotEmpty) out.add(MarkdownText(md));
    plain.clear();
  }

  var i = 0;
  while (i < lines.length) {
    final isTable =
        lines[i].trim().startsWith('|') &&
        i + 1 < lines.length &&
        _rule.hasMatch(lines[i + 1].trim());
    if (!isTable) {
      plain.add(lines[i++]);
      continue;
    }
    flush();
    final head = _cells(lines[i]);
    final rows = <List<String>>[];
    i += 2;
    while (i < lines.length && lines[i].trim().startsWith('|')) {
      rows.add(_cells(lines[i++]));
    }
    out.add(DataGridView(columns: head, rows: rows));
  }
  flush();
  return out;
}
