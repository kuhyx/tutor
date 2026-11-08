part of 'fit_pages.dart';

class _Slot extends ContainerBoxParentData<RenderBox>;

/// Lays its children out as one tall column and paints one page of it.
class RenderFitPages extends RenderBox
    with
        ContainerRenderObjectMixin<RenderBox, _Slot>,
        RenderBoxContainerDefaultsMixin<RenderBox, _Slot> {
  /// Creates the render object.
  new({
    required this._controller,
    required this._gap,
    required this._barExtent,
  });

  FitPageController _controller;
  double _gap;
  double _barExtent;
  List<double> _starts = const [0];
  double _end = 0;
  double _pageExtent = 0;

  /// The controller.
  FitPageController get controller => _controller;
  set controller(FitPageController value) {
    if (value == _controller) return;
    if (attached) _controller.removeListener(markNeedsPaint);
    _controller = value;
    if (attached) _controller.addListener(markNeedsPaint);
    markNeedsLayout();
  }

  /// Space between children.
  double get gap => _gap;
  set gap(double value) {
    if (value == _gap) return;
    _gap = value;
    markNeedsLayout();
  }

  /// Height the pager bar takes once there are pages.
  double get barExtent => _barExtent;
  set barExtent(double value) {
    if (value == _barExtent) return;
    _barExtent = value;
    markNeedsLayout();
  }

  int get _page => math.min(_controller.page, _starts.length - 1);

  double get _offset => _starts[_page];

  /// Visible height of the shown page.
  double get _window {
    final next = _page + 1 < _starts.length ? _starts[_page + 1] : _end;
    return math.min(_pageExtent, next - _offset);
  }

  @override
  void attach(PipelineOwner owner) {
    super.attach(owner);
    _controller.addListener(markNeedsPaint);
  }

  @override
  void detach() {
    _controller.removeListener(markNeedsPaint);
    super.detach();
  }

  @override
  void setupParentData(RenderBox child) {
    if (child.parentData is! _Slot) child.parentData = _Slot();
  }

  @override
  Size computeDryLayout(BoxConstraints constraints) {
    final inner = BoxConstraints.tightFor(width: constraints.maxWidth);
    var y = 0.0;
    var child = firstChild;
    while (child != null) {
      if (child != firstChild) y += _gap;
      y += child.getDryLayout(inner).height;
      child = childAfter(child);
    }
    return constraints.constrain(Size(constraints.maxWidth, y));
  }

  @override
  void performLayout() {
    final width = constraints.maxWidth;
    final inner = BoxConstraints.tightFor(width: width);
    final bounds = <(double, double)>[];
    var y = 0.0;
    var child = firstChild;
    while (child != null) {
      if (bounds.isNotEmpty) y += _gap;
      child.layout(inner, parentUsesSize: true);
      (child.parentData! as _Slot).offset = Offset(0, y);
      bounds.add((y, y + child.size.height));
      y += child.size.height;
      child = childAfter(child);
    }
    _end = y;
    // What the shown page starts with, to keep it in view after a resize
    // (the keyboard opening re-cuts the pages).
    final anchor = _starts[math.min(_controller.page, _starts.length - 1)];
    size = constraints.constrain(Size(width, y));
    _pageExtent = y <= size.height ? size.height : size.height - _barExtent;
    _starts = _breaks(bounds, math.max(1, _pageExtent));
    final lastTop = bounds.isEmpty ? 0.0 : bounds.last.$1;
    final shown = _pageOf(anchor);
    if (_controller._laidOut(_starts.length, _pageOf(lastTop), shown)) {
      final c = _controller;
      SchedulerBinding.instance.addPostFrameCallback((_) => c._changed());
    }
  }

  /// The page holding column offset [y].
  int _pageOf(double y) {
    var page = 0;
    for (var i = 0; i < _starts.length; i++) {
      if (_starts[i] <= y + 0.01) page = i;
    }
    return page;
  }

  /// Page starts: a page ends before the child that would not fit, and a
  /// child taller than a page is cut into page-high slices.
  static List<double> _breaks(List<(double, double)> bounds, double extent) {
    final starts = <double>[0];
    var s = 0.0;
    for (final (top, bottom) in bounds) {
      if (bottom - s <= extent + 0.01) continue;
      if (top > s) {
        s = top;
        starts.add(s);
      }
      while (bottom - s > extent + 0.01) {
        s += extent;
        starts.add(s);
      }
    }
    return starts;
  }

  @override
  void paint(PaintingContext context, Offset offset) {
    final window = Rect.fromLTWH(0, 0, size.width, _window);
    context.pushClipRect(needsCompositing, offset, window, (ctx, at) {
      var child = firstChild;
      while (child != null) {
        final slot = child.parentData! as _Slot;
        final top = slot.offset.dy - _offset;
        if (top < window.bottom && top + child.size.height > 0) {
          ctx.paintChild(child, at + Offset(0, top));
        }
        child = slot.nextSibling;
      }
    });
  }

  @override
  void applyPaintTransform(RenderBox child, Matrix4 transform) {
    final slot = child.parentData! as _Slot;
    transform.translateByDouble(0, slot.offset.dy - _offset, 0, 1);
  }

  @override
  Rect? describeApproximatePaintClip(RenderObject child) =>
      Rect.fromLTWH(0, 0, size.width, _window);

  @override
  bool hitTestChildren(BoxHitTestResult result, {required Offset position}) {
    if (position.dy < 0 || position.dy >= _window) return false;
    var child = lastChild;
    while (child != null) {
      final slot = child.parentData! as _Slot;
      final at = Offset(0, slot.offset.dy - _offset);
      final hit = result.addWithPaintOffset(
        offset: at,
        position: position,
        hitTest: (r, p) => child!.hitTest(r, position: p),
      );
      if (hit) return true;
      child = slot.previousSibling;
    }
    return false;
  }

  /// Turns to the page holding a descendant that asks to be seen (a focused
  /// field, its caret), since there is no scroll to bring it into view.
  @override
  void showOnScreen({
    RenderObject? descendant,
    Rect? rect,
    Duration duration = Duration.zero,
    Curve curve = Curves.ease,
  }) {
    if (descendant != null && descendant != this && _starts.length > 1) {
      final local = MatrixUtils.transformRect(
        descendant.getTransformTo(this),
        rect ?? descendant.paintBounds,
      );
      // The centre: a caret rect arrives padded, reaching above its field.
      _controller.goTo(_pageOf(local.center.dy + _offset));
    }
    super.showOnScreen(duration: duration, curve: curve);
  }
}
