/// Content text: words kuhy or the tutor wrote, which the app only shows
/// (deck cards, tutor replies, typed messages, subject / module / plan /
/// card names, session ids). Everything else on screen is text-free
/// (textgate); `test/ui/no_words_test.dart` allows letters only under a
/// [ContentText] or a [ContentScope].
library;

import 'package:flutter/material.dart';

/// Marks a subtree whose painted words are content (markdown bodies,
/// selectable replies, rich card text).
class ContentScope extends StatelessWidget {
  /// Creates the marker around [child].
  const new({required this.child, super.key});

  /// The content.
  final Widget child;

  @override
  Widget build(BuildContext context) => child;
}

/// A [Text] whose words are content.
class ContentText extends StatelessWidget {
  /// Shows [data].
  const new(
    String this.data, {
    this.style,
    this.maxLines,
    this.overflow,
    this.textAlign,
    this.softWrap,
    super.key,
  }) : span = null;

  /// Shows a rich [span] (all of it content).
  const new rich(
    InlineSpan this.span, {
    this.style,
    this.maxLines,
    this.overflow,
    this.textAlign,
    this.softWrap,
    super.key,
  }) : data = null;

  /// The plain text, or null for [span].
  final String? data;

  /// The rich text, or null for [data].
  final InlineSpan? span;

  /// As [Text.style].
  final TextStyle? style;

  /// As [Text.maxLines].
  final int? maxLines;

  /// As [Text.overflow].
  final TextOverflow? overflow;

  /// As [Text.textAlign].
  final TextAlign? textAlign;

  /// As [Text.softWrap].
  final bool? softWrap;

  @override
  Widget build(BuildContext context) {
    final rich = span;
    return rich == null
        ? Text(
            data!,
            style: style,
            maxLines: maxLines,
            overflow: overflow,
            textAlign: textAlign,
            softWrap: softWrap,
          )
        : Text.rich(
            rich,
            style: style,
            maxLines: maxLines,
            overflow: overflow,
            textAlign: textAlign,
            softWrap: softWrap,
          );
  }
}
