import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/session/markdown.dart';

void main() {
  test('paragraphs keep line breaks and inline styles', () {
    final blocks = parseMarkdown('A **bold** *em* `code` end\nnext\n\n\nB');
    expect(blocks, hasLength(2));
    expect(blocks.first.kind, MdBlockKind.paragraph);
    expect(blocks.first.lines.first, [
      const MdSpan('A '),
      const MdSpan('bold', MdStyle.bold),
      const MdSpan(' '),
      const MdSpan('em', MdStyle.em),
      const MdSpan(' '),
      const MdSpan('code', MdStyle.code),
      const MdSpan(' end'),
    ]);
    expect(blocks.first.lines[1], [const MdSpan('next')]);
    expect(blocks.last.lines.single.single.text, 'B');
  });

  test('lists: bullets and numbered; a mixed block stays a paragraph', () {
    final b = parseMarkdown('- one\n* two\n\n1. a\n2. b\n\n- x\nplain');
    expect(b.map((x) => x.kind), [
      MdBlockKind.bullets,
      MdBlockKind.numbered,
      MdBlockKind.paragraph,
    ]);
    expect(b[0].lines.map((l) => l.single.text), ['one', 'two']);
    expect(b[1].lines.map((l) => l.single.text), ['a', 'b']);
  });

  test('no HTML path: tags stay literal text; blank text has no blocks', () {
    final spans = parseInline('<b>x</b> **');
    expect(spans.single, const MdSpan('<b>x</b> **'));
    expect(parseMarkdown('  \n\n '), isEmpty);
    expect(parseInline(''), isEmpty);
  });

  test('MdSpan equality and toString', () {
    expect(const MdSpan('a').hashCode, const MdSpan('a').hashCode);
    expect(const MdSpan('a') == const MdSpan('a', MdStyle.em), isFalse);
    expect(const MdSpan('a', MdStyle.code).toString(), 'code(a)');
  });
}
