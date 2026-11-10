/// Text fields without placeholder or floating label (textgate): a leading
/// glyph names the field, the old label is spoken only.
library;

import 'package:flutter/material.dart';

/// The decoration of a field named by [icon] (no hint, no label).
InputDecoration iconDecoration(
  IconData icon, {
  Widget? suffixIcon,
  bool dense = false,
  InputBorder? border,
}) => InputDecoration(
  prefixIcon: Icon(icon),
  suffixIcon: suffixIcon,
  isDense: dense,
  border: border ?? const OutlineInputBorder(),
);

/// Gives the text field [child] the spoken label [semanticLabel], merged
/// into the field's own node (no dead duplicate textbox).
class FieldLabel extends StatelessWidget {
  /// Creates the label.
  const new({required this.semanticLabel, required this.child, super.key});

  /// The old field label, spoken only.
  final String semanticLabel;

  /// The field.
  final Widget child;

  @override
  Widget build(BuildContext context) => MergeSemantics(
    child: Semantics(label: semanticLabel, child: child),
  );
}
