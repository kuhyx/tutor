import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/focus/focus_models.dart';
import 'package:tutor/widgets/content_text.dart';

/// `mm:ss` of [d].
String focusClock(Duration d) {
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(d.inMinutes)}:${two(d.inSeconds % 60)}';
}

/// The gates the project turns off, then those it keeps, as chips.
class FocusGates extends StatelessWidget {
  /// Creates the chips for [status].
  const new(this.status, {super.key});

  /// Today's project and the gate list.
  final FocusStatus status;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Wrap(
      spacing: AppSpacing.sm,
      runSpacing: AppSpacing.xs,
      alignment: WrapAlignment.center,
      children: [
        for (final label in gateLabels(status, off: true))
          Chip(
            avatar: const Icon(Icons.block, size: 16),
            label: ContentText(label),
            side: BorderSide(color: scheme.outlineVariant),
          ),
        for (final label in gateLabels(status, off: false))
          Chip(
            avatar: const Icon(Icons.check, size: 16),
            label: ContentText(label),
          ),
      ],
    );
  }
}

/// A date shown as a field; [onTap] picks it (null: locked).
class DateField extends StatelessWidget {
  /// Creates the field.
  const new(this.label, this.text, {required this.onTap, super.key});

  /// Field label.
  final String label;

  /// The date, as shown.
  final String text;

  /// Opens the picker.
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => InkWell(
    onTap: onTap,
    child: InputDecorator(
      decoration: InputDecoration(
        labelText: label,
        suffixIcon: const Icon(Icons.event),
      ),
      child: Text(text),
    ),
  );
}

/// A whole-number field.
Widget numberField(
  TextEditingController c,
  String label,
  ValueChanged<String> onChanged,
) => TextField(
  controller: c,
  keyboardType: TextInputType.number,
  decoration: InputDecoration(labelText: label),
  onChanged: onChanged,
);
