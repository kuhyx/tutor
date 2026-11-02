/// A multi-line code field: monospace, line numbers that follow wrapped
/// lines, no autocorrect.
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

/// The editor over [controller].
class SqlEditor extends StatelessWidget {
  /// Creates the editor.
  const new({required this.controller, super.key});

  /// The SQL text.
  final TextEditingController controller;

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
}
