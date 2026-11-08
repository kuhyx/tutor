/// Phone layouts built on [FitPages] (build-mobile-app R7): a paged body
/// over pinned actions, a form, a capped block.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/ui/fit_pages.dart';
import 'package:tutor/ui/layout.dart';

/// Phone split: [body] (usually paged) above [bar], which stays in place on
/// every page and above the keyboard; the bar takes the bottom inset.
class FitSplit extends StatelessWidget {
  /// Creates the split.
  const new({required this.body, required this.bar, super.key});

  /// The part that pages.
  final Widget body;

  /// Actions kept on screen.
  final Widget bar;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Expanded(
        child: MediaQuery.removePadding(
          context: context,
          removeBottom: true,
          child: body,
        ),
      ),
      SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.md,
            0,
            AppSpacing.md,
            AppSpacing.sm,
          ),
          child: bar,
        ),
      ),
    ],
  );
}

/// A form: on a phone ([isCompact]) its [fields] page and [bar] stays in
/// place above the keyboard; elsewhere [wide] lays out fields then bar.
Widget fitForm(
  BuildContext context, {
  required List<Widget> fields,
  required List<Widget> bar,
  required Widget Function(List<Widget> all) wide,
}) => isCompact(context)
    ? FitSplit(
        body: FitPages(
          padding: const EdgeInsets.all(AppSpacing.md),
          children: fields,
        ),
        bar: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: bar,
        ),
      )
    : wide([...fields, ...bar]);

/// [child] in a capped box: on a phone ([isCompact]) paged (sliced when
/// taller than the box), elsewhere scrolled.
Widget fitScroll(
  BuildContext context, {
  required Widget child,
  EdgeInsets padding = EdgeInsets.zero,
  Key? key,
}) => isCompact(context)
    ? FitPages(key: key, padding: padding, children: [child])
    : SingleChildScrollView(key: key, padding: padding, child: child);

/// [children]: on a phone ([isCompact]) a page at a time ([pages]),
/// elsewhere a list ([scroll]).
Widget fitList(
  BuildContext context, {
  required List<Widget> children,
  EdgeInsets padding = EdgeInsets.zero,
  FitPageController? pages,
  ScrollController? scroll,
}) => isCompact(context)
    ? FitPages(controller: pages, padding: padding, children: children)
    : ListView(controller: scroll, padding: padding, children: children);

/// [child] Flexible on a phone, so a capped block shares a short screen
/// instead of overflowing it; as is elsewhere.
Widget fitFlex(BuildContext context, Widget child) =>
    isCompact(context) ? Flexible(child: child) : child;
