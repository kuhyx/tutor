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
