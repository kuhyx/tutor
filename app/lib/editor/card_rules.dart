/// The card editor's local checks (curriculum §3 limits), so an obviously
/// bad card is caught before a `card_edit` round trip. The worker still
/// fetches the source and verifies the excerpt verbatim; only it can.
library;

/// Front word limit.
const kFrontWords = 25;

/// Back word limit.
const kBackWords = 30;

/// Excerpt word range.
const kExcerptWords = (6, 40);

/// Words in [text].
int wordCount(String text) =>
    text.trim().split(RegExp(r'\s+')).where((w) => w.isNotEmpty).length;

/// Why the card cannot be sent; empty when it can.
List<String> cardProblems({
  required String front,
  required String back,
  required String source,
  required String excerpt,
}) {
  final (minEx, maxEx) = kExcerptWords;
  final f = wordCount(front);
  final b = wordCount(back);
  final e = wordCount(excerpt);
  final uri = Uri.tryParse(source.trim());
  return [
    if (f == 0 || f > kFrontWords) 'Front: 1-$kFrontWords words (has $f).',
    if (b == 0 || b > kBackWords) 'Back: 1-$kBackWords words (has $b).',
    if (uri == null || uri.scheme != 'https' || uri.host.isEmpty)
      'Source must be an https:// link.',
    if (e < minEx || e > maxEx)
      'Excerpt: $minEx-$maxEx words verbatim from the source (has $e).',
  ];
}

/// Host of [url] for a compact source link, or the url itself.
String hostOf(String url) {
  final host = Uri.tryParse(url)?.host ?? '';
  return host.isEmpty ? url : host;
}
