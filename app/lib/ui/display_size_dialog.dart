/// The "Display size" setting (Home's ⋮ menu): a slider over `UiZoom`,
/// 50%-200% of the automatic size for this screen, plus a reset glyph.
library;

import 'package:flutter/material.dart';
import 'package:tutor/ui/ui_zoom.dart';
import 'package:tutor/util/ui_scale.dart';
import 'package:tutor/widgets/spoken_label.dart';

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
        ],
      ),
      actions: [
        GlyphButton(
          icon: Icons.restart_alt,
          semanticLabel: 'Reset to auto',
          onPressed: zoom.reset,
        ),
        GlyphButton(
          icon: Icons.check,
          semanticLabel: 'Done',
          filled: true,
          onPressed: () => Navigator.of(context).pop(),
        ),
      ],
    );
  }
}
