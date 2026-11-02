/// A multi-line SQL field: monospace, line numbers that follow wrapped
/// lines, no autocorrect, and a row of symbols a phone keyboard buries.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/ui/sql/data_grid.dart';

const _strut = StrutStyle(
  fontFamily: 'monospace',
  fontSize: AppTextSize.label,
  height: 1.5,
  forceStrutHeight: true,
);
const _symbols = ['*', '(', ')', "'", ',', '=', '.', '%', '<', '>', '_'];

/// The editor over [controller]; [showKeys] adds the symbol row.
class SqlEditor extends StatelessWidget {
  /// Creates the editor.
  const new({required this.controller, this.showKeys = false, super.key});

  /// The SQL text.
  final TextEditingController controller;

  /// Show the symbol row (touch screens).
  final bool showKeys;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        DecoratedBox(
          decoration: BoxDecoration(
            border: Border.all(color: scheme.outline),
            borderRadius: BorderRadius.circular(AppRadius.sm),
          ),
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.sm),
            child: LayoutBuilder(
              builder: (context, box) => ListenableBuilder(
                listenable: controller,
                builder: (context, _) => _body(box.maxWidth, scheme),
              ),
            ),
          ),
        ),
        if (showKeys)
          ExcludeFocus(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  for (final s in _symbols)
                    TextButton(
                      key: ValueKey('key-$s'),
                      onPressed: () => _insert(s),
                      child: Text(s, style: sqlMono),
                    ),
                ],
              ),
            ),
          ),
      ],
    );
  }

  Widget _body(double width, ColorScheme scheme) {
    final lines = controller.text.split('\n');
    final digits = '${lines.length}'.length;
    final gutter = _measure('0' * digits, double.infinity).width;
    final field = width - gutter - AppSpacing.sm;
    int wraps(String line) =>
        _measure(line.isEmpty ? ' ' : line, field).lines - 1;
    final numbers = [
      for (final (i, line) in lines.indexed) '${i + 1}${'\n' * wraps(line)}',
    ].join('\n');
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: gutter,
          child: Text(
            numbers,
            key: const ValueKey('gutter'),
            textAlign: TextAlign.end,
            strutStyle: _strut,
            style: sqlMono.copyWith(color: scheme.outline),
          ),
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: TextField(
            key: const ValueKey('sql-editor'),
            controller: controller,
            minLines: 6,
            maxLines: null,
            keyboardType: TextInputType.multiline,
            autocorrect: false,
            enableSuggestions: false,
            smartDashesType: SmartDashesType.disabled,
            smartQuotesType: SmartQuotesType.disabled,
            style: sqlMono,
            strutStyle: _strut,
            decoration: const InputDecoration.collapsed(hintText: ''),
          ),
        ),
      ],
    );
  }

  ({double width, int lines}) _measure(String text, double maxWidth) {
    final p = TextPainter(
      text: TextSpan(text: text, style: sqlMono),
      textDirection: TextDirection.ltr,
      strutStyle: _strut,
    )..layout(maxWidth: maxWidth);
    final result = (width: p.width, lines: p.computeLineMetrics().length);
    p.dispose();
    return result;
  }

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
