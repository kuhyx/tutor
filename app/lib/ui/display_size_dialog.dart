/// The "Display size" setting (Home's ⋮ menu): a slider over `UiZoom`,
/// 50%-200% of the automatic size for this screen, plus Reset to auto.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/ui/ui_zoom.dart';
import 'package:tutor/util/ui_scale.dart';

/// Opens the setting over [context]'s route.
Future<void> showDisplaySize(BuildContext context) => showDialog<void>(
  context: context,
  builder: (_) => const DisplaySizeDialog(),
);

/// The slider; applies on release (the dialog itself rescales, so applying
/// mid-drag would move the thumb out from under the finger).
class DisplaySizeDialog extends StatefulWidget {
  /// Creates the dialog.
  const new({super.key});

  @override
  State<DisplaySizeDialog> createState() => _DisplaySizeDialogState();
}

class _DisplaySizeDialogState extends State<DisplaySizeDialog> {
  /// The thumb while dragging; null = show the live zoom (which Ctrl + /
  /// Ctrl - can change while the dialog is open).
  double? _drag;

  @override
  Widget build(BuildContext context) {
    final zoom = UiZoom.controllerOf(context)!;
    final shown = _drag ?? UiZoom.of(context);
    final percent = '${(shown * 100).round()}%';
    return AlertDialog(
      title: const Text('Display size'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(percent, style: Theme.of(context).textTheme.headlineSmall),
          Slider(
            min: kMinZoom,
            max: kMaxZoom,
            divisions: ((kMaxZoom - kMinZoom) * kZoomStepsPerUnit).round(),
            value: shown,
            label: percent,
            onChanged: (v) => setState(() => _drag = v),
            onChangeEnd: (v) async {
              await zoom.set(v);
              if (mounted) setState(() => _drag = null);
            },
          ),
          const SizedBox(height: AppSpacing.sm),
          const Text(
            'Of the automatic size for this screen, on this device only. '
            'Keyboard: Ctrl + / Ctrl - / Ctrl 0.',
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: zoom.reset, child: const Text('Reset to auto')),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Done'),
        ),
      ],
    );
  }
}
