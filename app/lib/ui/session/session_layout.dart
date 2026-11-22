/// The Session screen's body: the chat alone, or, on wide windows, the chat
/// at a reading width with the side panel beside it.
library;

import 'package:flutter/material.dart';

/// Width from which the side panel sits beside the chat.
const kWideLayout = 900.0;

/// Widest the chat column gets (prose stays readable on wide windows).
const kChatMaxWidth = 960.0;

/// The side panel's width for a window [width] wide (wide layout only).
double sideWidth(double width) => (width * 0.25).clamp(300, 420);

/// The body under the Session screen's bar.
class SessionBody extends StatelessWidget {
  /// Creates the body; [width] is the window's, used when [wide].
  const new({
    required this.wide,
    required this.width,
    required this.chat,
    required this.side,
    this.fixedSide,
    super.key,
  });

  /// The side panel's fixed width; null = [sideWidth] of the window.
  final double? fixedSide;

  /// Side panel inline ([kWideLayout] and up).
  final bool wide;

  /// The window's width.
  final double width;

  /// The chat column.
  final Widget chat;

  /// The side panel.
  final Widget side;

  // Under an AppBar the top inset is already 0; without one the body keeps
  // clear of the status bar. The bottom keeps the row off the gesture bar
  // (0 with the keyboard up). Same tree either way, so the box keeps its
  // focus.
  @override
  Widget build(BuildContext context) => SafeArea(
    child: wide
        ? Row(
            children: [
              // The chat keeps a reading width; the panel grows with the
              // window so long card fronts wrap, not clip.
              Expanded(
                child: Align(
                  alignment: Alignment.topCenter,
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: kChatMaxWidth),
                    child: chat,
                  ),
                ),
              ),
              const VerticalDivider(width: 1),
              SizedBox(width: fixedSide ?? sideWidth(width), child: side),
            ],
          )
        : chat,
  );
}
