import 'package:flutter/material.dart';
import 'package:tutor/ui/sql/data_grid.dart';

/// Symbols a phone keyboard buries; `'  '` is the tab (two spaces).
const codeSymbolKeys = [
  '(',
  ')',
  ',',
  "'",
  '"',
  '=',
  '<',
  '>',
  '*',
  '_',
  ';',
  '[',
  ']',
  ':',
  '  ',
  '{',
  '}',
  '.',
  '%',
  '+',
  '-',
  '/',
  '!',
  '|',
];

/// A scrolling row of symbol keys that type into `controller` at the cursor
/// without taking focus, so the keyboard stays up. Pin it above the keyboard.
class CodeSymbolBar extends StatelessWidget {
  /// Creates the bar.
  const new({required this.controller, super.key});

  /// The text the keys insert into.
  final TextEditingController controller;

  @override
  Widget build(BuildContext context) => ExcludeFocus(
    child: SizedBox(
      height: 44,
      child: SingleChildScrollView(
        key: const ValueKey('symbol-bar'),
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            for (final s in codeSymbolKeys)
              TextButton(
                key: ValueKey('key-$s'),
                onPressed: () => _insert(s),
                child: Text(s.trim().isEmpty ? '⇥' : s, style: sqlMono),
              ),
          ],
        ),
      ),
    ),
  );

  void _insert(String symbol) {
    final text = controller.text;
    final sel = controller.selection;
    final start = sel.isValid ? sel.start : text.length;
    final end = sel.isValid ? sel.end : text.length;
    controller.value = TextEditingValue(
      text: text.replaceRange(start, end, symbol),
      selection: TextSelection.collapsed(offset: start + symbol.length),
    );
  }
}

/// `child` filling the height with a [CodeSymbolBar] pinned under it when
/// `show` (touch screens).
class WithSymbolBar extends StatelessWidget {
  /// Creates the pair.
  const new({
    required this.controller,
    required this.child,
    required this.show,
    super.key,
  });

  /// The text the keys insert into.
  final TextEditingController controller;

  /// The editor page.
  final Widget child;

  /// Whether the bar shows.
  final bool show;

  @override
  Widget build(BuildContext context) => !show
      ? child
      : Column(
          children: [
            Expanded(child: child),
            CodeSymbolBar(controller: controller),
          ],
        );
}
