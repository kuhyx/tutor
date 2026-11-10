/// The app theme without painted tooltips (textgate): the framework's own
/// tooltips (Back, Close, the menu button) stay as spoken labels but never
/// show on long-press or hover. A tooltip kuhy approved opts back in with
/// [approvedTooltip].
library;

import 'package:flutter/material.dart';

/// A wait no pointer ever reaches: hover never shows a tooltip.
const spokenOnlyWait = Duration(days: 365);

/// [base] with tooltips spoken only.
ThemeData textFreeTheme(ThemeData base) => base.copyWith(
  tooltipTheme: base.tooltipTheme.copyWith(
    triggerMode: TooltipTriggerMode.manual,
    waitDuration: spokenOnlyWait,
  ),
);

/// A tooltip kuhy approved (text-approvals.json): shown as usual.
Widget approvedTooltip({required String message, required Widget child}) =>
    Tooltip(
      message: message,
      triggerMode: TooltipTriggerMode.longPress,
      waitDuration: const Duration(milliseconds: 500),
      child: child,
    );
