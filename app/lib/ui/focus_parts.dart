import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/ui/unbacked_mark.dart';

/// New, edit and end buttons under the timer; wraps at a large font
/// instead of overflowing.
class ProjectActions extends StatelessWidget {
  /// Creates the buttons.
  const new({
    required this.onNew,
    required this.onEdit,
    required this.onEnd,
    super.key,
  });

  /// New project.
  final VoidCallback onNew;

  /// Edit the active project.
  final VoidCallback onEdit;

  /// End the active project.
  final VoidCallback onEnd;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Wrap(
      alignment: WrapAlignment.spaceBetween,
      children: [
        TextButton(onPressed: onNew, child: Text(l.newProject)),
        TextButton(onPressed: onEdit, child: Text(l.editProject)),
        TextButton(onPressed: onEnd, child: Text(l.endProject)),
      ],
    );
  }
}

/// The screen with no active project: only the way to make one.
class NoProject extends StatelessWidget {
  /// Creates the view.
  const new({required this.onNew, super.key});

  /// New project.
  final VoidCallback onNew;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      children: [
        Expanded(
          child: EmptyState(
            icon: Icons.center_focus_strong_outlined,
            title: l.noProject,
            message: '',
          ),
        ),
        FilledButton.icon(
          onPressed: onNew,
          icon: const Icon(Icons.add),
          label: Text(l.newProject),
        ),
      ],
    );
  }
}

/// The unbacked-minutes mark and its gap; nothing when there are none.
List<Widget> unbackedRow(int minutes) => [
  if (minutes > 0) UnbackedMark(minutes, key: const ValueKey('unbacked')),
  if (minutes > 0) const SizedBox(height: AppSpacing.xs),
];

/// The big start / stop button of the timer.
class StartStopButton extends StatelessWidget {
  /// Creates the button; [running] picks its glyph and label.
  const new({required this.running, required this.onPressed, super.key});

  /// The timer is running (the button stops it).
  final bool running;

  /// Starts or stops the timer.
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return SizedBox(
      height: 72,
      child: FilledButton.icon(
        onPressed: onPressed,
        icon: Icon(running ? Icons.stop : Icons.play_arrow),
        label: Text(running ? l.stop : l.start),
      ),
    );
  }
}
