/// The Session screen's Scaffold: the bar (title, stats, actions), the end
/// drawer and the body with a wheel that scrolls the chat.
library;

import 'package:flutter/material.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/session/leetcode_label.dart';
import 'package:tutor/ui/session/leetcode_stats.dart';
import 'package:tutor/ui/session/session_actions.dart';
import 'package:tutor/ui/session/session_bar.dart';
import 'package:tutor/ui/session/session_chrome.dart';
import 'package:tutor/ui/session/session_header.dart';
import 'package:tutor/ui/session/session_layout.dart';

/// The Session screen's Scaffold around [chat] and [side].
class SessionFrame extends StatelessWidget {
  /// Creates the frame; [wide] and [desk] come from the window's [width].
  const new({
    required this.scaffoldKey,
    required this.keyboard,
    required this.wide,
    required this.desk,
    required this.width,
    required this.title,
    required this.meta,
    required this.sid,
    required this.today,
    required this.now,
    required this.card,
    required this.mastered,
    required this.scroll,
    required this.chat,
    required this.side,
    super.key,
  });

  /// The Scaffold's key (`SessionKeyboard` closes its drawer).
  final GlobalKey<ScaffoldState> scaffoldKey;

  /// Phone keyboard up: the bar (and its sidebar button) goes.
  final bool keyboard;

  /// The side panel sits beside the chat (else in the end drawer).
  final bool wide;

  /// Wide on a desktop: the actions and stats in the bar, the card pane.
  final bool desk;

  /// The window's width.
  final double width;

  /// The subject's name (content); none before it loads.
  final String? title;

  /// The session on screen (the bar's stats, the card pane).
  final SessionMeta? meta;

  /// The session on screen (the bar's actions).
  final String? sid;

  /// The day's totals (the bar's stats).
  final Today? today;

  /// Clock for the stats.
  final DateTime Function()? now;

  /// The card actions (the desktop bar).
  final CardActions card;

  /// The concepts the Known glyph lists.
  final List<String> mastered;

  /// The chat's scroll, driven by a wheel anywhere.
  final ScrollController scroll;

  /// The chat column.
  final Widget chat;

  /// The side panel: the drawer's content, or inline on a phone.
  final Widget side;

  @override
  Widget build(BuildContext context) => Scaffold(
    key: scaffoldKey,
    appBar: keyboard
        ? null
        : sessionAppBar(
            // A theory lesson is titled by its unit, under a pencil.
            title: meta?.leetcode?.unit ?? title,
            lead: meta?.leetcode == null ? null : kUnitIcon,
            spoken: meta?.leetcode == null
                ? null
                : leetcodeLines(meta!.leetcode!).unit,
            // Off the desktop its stats get a line of their own.
            row: !desk && meta?.leetcode != null
                ? barStats(meta, today, now)
                : null,
            twoLines: desk && width < kBarOneLine,
            stats: desk ? barStats(meta, today, now) : null,
            actions: sessionActions(
              sid: sid,
              wide: wide,
              card: desk ? card : null,
              mastered: mastered,
            ),
          ),
    endDrawer: wide ? null : Drawer(child: SafeArea(child: side)),
    drawerEnableOpenDragGesture: !keyboard,
    endDrawerEnableOpenDragGesture: !keyboard,
    // A wheel anywhere, the empty margins too, scrolls the chat.
    body: Listener(
      behavior: HitTestBehavior.translucent,
      onPointerSignal: (e) => forwardWheel(scroll, e, reversed: !desk),
      child: SessionBody(
        wide: wide,
        width: width,
        chat: chat,
        fixedSide: desk ? kCardPaneWidth : null,
        side: desk ? SessionCardPane(meta: meta) : side,
      ),
    ),
  );
}
