/// How much to enlarge the whole UI for the screen it is on.
///
/// The layout is drawn for a full HD screen at scale 1. A 4K or QHD monitor
/// at device pixel ratio 1 (kuhy's X11 desktop has no Xft.dpi, so Chrome
/// reports 1) would show it at half or two thirds of its intended physical
/// size: unreadable (kuhy, 2026-10-12). The scale comes from the DISPLAY,
/// not the window, so a half-width tile on a 4K monitor is as legible as a
/// full-screen window; it is per display, so the 4K and the QHD monitor
/// each get their own (a process-wide `--force-device-scale-factor` could
/// not). Phones and laptops (logical screens at or below full HD) stay at 1.
library;

import 'dart:math' as math;
import 'dart:ui' show Size;

/// The screen a scale of 1 is drawn for (landscape).
const Size kReferenceDisplay = Size(1920, 1080);

/// The largest scale (an 8K monitor at DPR 1 stays usable, not huge).
const double kMaxUiScale = 2.5;

/// The UI scale for a display of [logical] size (physical / its DPR), in
/// either orientation; 1 for anything up to full HD, to 2 decimals.
double uiScaleFor(Size logical) {
  if (logical.isEmpty) return 1;
  final long = math.max(logical.width, logical.height);
  final short = math.min(logical.width, logical.height);
  final s = math.min(
    long / kReferenceDisplay.width,
    short / kReferenceDisplay.height,
  );
  return (s.clamp(1.0, kMaxUiScale) * 100).round() / 100;
}
