/// Phone pages (build-mobile-app R7): a column of children shown one page
/// at a time, with previous/next under it, instead of a scroll. Pages break
/// between children; a child taller than a page is shown in slices.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/scheduler.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';

part 'fit_pages_render.dart';

/// The page shown and how many there are.
class FitPageController extends ChangeNotifier {
  int _page = 0;
  int _count = 1;
  bool _toLast = false;

  /// Shown page, from 0.
  int get page => _page;

  /// Pages at the last layout.
  int get count => _count;

  /// Shows [page], clamped.
  void goTo(int page) {
    final p = page.clamp(0, _count - 1);
    if (p == _page) return;
    _page = p;
    notifyListeners();
  }

  /// The previous page.
  void prev() => goTo(_page - 1);

  /// The next page.
  void next() => goTo(_page + 1);

  /// After the next layout, shows the page where the last child starts
  /// (a new chat turn: read from its top).
  void toLast() => _toLast = true;

  /// Takes [count] from a layout at once, so a `goTo` later in the same
  /// frame (a focused field asking to be shown) clamps to the new count;
  /// true when listeners (the bar) must hear of it after the frame.
  bool _laidOut(int count, int lastStart, int shown) {
    final page = _toLast ? lastStart : shown;
    _toLast = false;
    if (count == _count && page == _page) return false;
    _count = count;
    _page = page;
    return true;
  }

  void _changed() => notifyListeners();
}

/// Height of the previous/next bar.
const double kFitPagerHeight = 48;

/// [children] one page at a time; the bar shows once there are two pages.
class FitPages extends StatefulWidget {
  /// Creates the pages.
  const new({
    required this.children,
    this.controller,
    this.gap = 0,
    this.padding = EdgeInsets.zero,
    super.key,
  });

  /// Content, top to bottom.
  final List<Widget> children;

  /// Owner of the page; null = its own.
  final FitPageController? controller;

  /// Space between children.
  final double gap;

  /// Space around the content on every page.
  final EdgeInsets padding;

  @override
  State<FitPages> createState() => _FitPagesState();
}

class _FitPagesState extends State<FitPages> {
  FitPageController? _own;

  FitPageController get _c =>
      widget.controller ?? (_own ??= FitPageController());

  @override
  void dispose() {
    _own?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Stack(
    children: [
      // Sized by the column: all the room it is given once it pages,
      // only its content's height (loose constraints) while it fits.
      Padding(
        padding: widget.padding,
        child: _PagedColumn(
          controller: _c,
          gap: widget.gap,
          barExtent: kFitPagerHeight - widget.padding.bottom,
          children: widget.children,
        ),
      ),
      Positioned(
        left: 0,
        right: 0,
        bottom: 0,
        child: FitPagerBar(controller: _c),
      ),
    ],
  );
}

/// `‹ n/m ›`; nothing while there is one page.
class FitPagerBar extends StatelessWidget {
  /// Creates the bar.
  const new({required this.controller, super.key});

  /// The pages it moves.
  final FitPageController controller;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: controller,
    builder: (context, _) {
      final c = controller;
      if (c.count < 2) return const SizedBox.shrink();
      final l10n = AppLocalizations.of(context);
      return SizedBox(
        height: kFitPagerHeight,
        child: Material(
          color: Theme.of(context).colorScheme.surface,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              IconButton(
                key: const ValueKey('fit-prev'),
                onPressed: c.page > 0 ? c.prev : null,
                icon: const Icon(
                  Icons.chevron_left,
                  semanticLabel: 'Previous page',
                ),
              ),
              Text(l10n.stepOf(c.page + 1, c.count)),
              IconButton(
                key: const ValueKey('fit-next'),
                onPressed: c.page < c.count - 1 ? c.next : null,
                icon: const Icon(
                  Icons.chevron_right,
                  semanticLabel: 'Next page',
                ),
              ),
            ],
          ),
        ),
      );
    },
  );
}

class _PagedColumn extends MultiChildRenderObjectWidget {
  const new({
    required this.controller,
    required this.gap,
    required this.barExtent,
    required super.children,
  });

  final FitPageController controller;
  final double gap;
  final double barExtent;

  @override
  RenderFitPages createRenderObject(BuildContext context) =>
      RenderFitPages(controller: controller, gap: gap, barExtent: barExtent);

  @override
  void updateRenderObject(BuildContext context, RenderFitPages r) => r
    ..controller = controller
    ..gap = gap
    ..barExtent = barExtent;
}
