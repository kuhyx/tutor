/// [text] unchanged, or an [ArgumentError] when it is over [max] chars: a
/// request body's size limit (DOCS-contract §4), checked before sending.
String capText(String text, int max) {
  if (text.length > max) {
    throw ArgumentError.value(text.length, 'text', 'longer than $max chars');
  }
  return text;
}
