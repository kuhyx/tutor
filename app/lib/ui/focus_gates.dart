import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/focus/focus_models.dart';

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
            label: Text(label),
            side: BorderSide(color: scheme.outlineVariant),
          ),
        for (final label in gateLabels(status, off: false))
          Chip(avatar: const Icon(Icons.check, size: 16), label: Text(label)),
      ],
    );
  }
}
