/// The session's turns: on a phone ([isCompact]) a page at a time, the
/// newest shown from its top (build-mobile-app R7); on the desktop a
/// reversed list (offset 0 = newest: late pictures above never push the
/// bottom away).
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/session/session_feed.dart';
import 'package:tutor/ui/fit_pages.dart';
import 'package:tutor/ui/layout.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/session/collapsed_tile.dart';
import 'package:tutor/ui/session/message_tile.dart';
import 'package:tutor/ui/session/thinking_panel.dart';

/// Every turn, the pending learner text and the live trace.
class ChatTurns extends StatelessWidget {
  /// Creates the turns.
  const new({
    required this.messages,
    required this.boxes,
    required this.busy,
    required this.view,
    required this.services,
    required this.keyboard,
    required this.pages,
    required this.scroll,
    super.key,
  });

  /// The turns so far.
  final List<KeyedMessage> messages;

  /// The latest tutor turn's questions show as answer boxes.
  final bool boxes;

  /// The turn in flight, if any.
  final Busy? busy;

  /// The session.
  final SessionView view;

  /// For reports.
  final TutorServices services;

  /// The keyboard is up: the latest tutor turn collapses.
  final bool keyboard;

  /// The phone's pages.
  final FitPageController pages;

  /// The desktop's scroll.
  final ScrollController scroll;

  @override
  Widget build(BuildContext context) {
    final busy = this.busy;
    final turns = [
      for (final (i, m) in messages.indexed)
        _tile(context, m, latest: i == messages.length - 1),
      if (busy != null && (busy.text ?? '').isNotEmpty)
        MessageTile(
          message: Message(role: 'learner', text: busy.text!),
          pending: true,
        ),
      if (busy != null) liveTrace(busy, view.progress),
    ];
    if (isCompact(context)) {
      return FitPages(
        controller: pages,
        padding: const EdgeInsets.all(AppSpacing.md),
        children: turns,
      );
    }
    return ListView(
      controller: scroll,
      reverse: true,
      padding: const EdgeInsets.all(AppSpacing.md),
      children: turns.reversed.toList(),
    );
  }

  Widget _tile(BuildContext context, KeyedMessage m, {required bool latest}) {
    final tutor = m.message.role == 'tutor';
    final tile = MessageTile(
      message: m.message,
      questionsAsBoxes: boxes && latest,
      onReport: tutor
          ? () => showReport(
              context,
              services,
              route: '/session',
              session: view.sid,
              msg: m.key,
              preview: m.message.text,
            )
          : null,
    );
    return keyboard && latest && tutor
        ? CollapsedTile(message: m.message, full: tile)
        : tile;
  }
}
