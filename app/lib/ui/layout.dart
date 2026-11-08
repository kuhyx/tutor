/// Wide-window layout: two columns side by side where a screen has two
/// kinds of content, one centred column below that width. Widths are
/// logical pixels after `UiScale`, so a 4K monitor lays out like full HD.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/ui/common.dart';

/// From this width a two-column page shows both columns.
const kTwoColumns = 1200.0;

/// Widest a two-column page gets.
const kTwoColumnMaxWidth = 1360.0;

/// Below this device width (dp) a screen uses its phone fit layout.
const kCompactWidth = 600.0;

/// Up to this device height (dp) a screen uses its phone fit layout.
const kCompactHeight = 950.0;

/// A phone-sized screen: fixed pages, never a scroll (build-mobile-app R7).
/// Read from the view in device dp, before `UiScale`: the phone's default
/// 90% zoom makes the app's logical size 457x1016, which would fail the
/// height bound, yet only adds room to a layout that fits 411x914.
bool isCompact(BuildContext context) {
  final view = View.of(context);
  final size = view.physicalSize / view.devicePixelRatio;
  return size.width < kCompactWidth && size.height <= kCompactHeight;
}

/// [first] beside [second] on wide windows, one under the other otherwise.
class TwoColumnPage extends StatelessWidget {
  /// Creates the page; [firstFlex] : [secondFlex] split the width.
  const new({
    required this.first,
    required this.second,
    this.firstFlex = 1,
    this.secondFlex = 1,
    super.key,
  });

  /// The left (or upper) column.
  final List<Widget> first;

  /// The right (or lower) column.
  final List<Widget> second;

  /// Left share.
  final int firstFlex;

  /// Right share.
  final int secondFlex;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, box) {
      if (box.maxWidth < kTwoColumns) {
        return PageList(children: [...first, ...second]);
      }
      Widget column(List<Widget> children) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: children,
      );
      return Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: kTwoColumnMaxWidth),
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(flex: firstFlex, child: column(first)),
                const SizedBox(width: AppSpacing.xl),
                Expanded(flex: secondFlex, child: column(second)),
              ],
            ),
          ),
        ),
      );
    },
  );
}
