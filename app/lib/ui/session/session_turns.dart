/// The session's turns: on a phone ([isCompact]) a page at a time, the
/// newest shown from its top (build-mobile-app R7); on the desktop a
/// reversed list (offset 0 = newest: late pictures above never push the
/// bottom away); on a wide desktop window ([ChatTurns.panel]) one scroll
/// whose offset 0 is the latest turn's top, right under the bar, with the
/// answer panel after it and older turns growing upward above it.
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
    this.panel,
    super.key,
  });

  /// Wide desktop: the status, Card done and composer, right after the
  /// latest turn in the same scroll (null: the panel is pinned below).
  final Widget? panel;

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
    if (panel case final p?) return _desk(turns, p);
    return ListView(
      controller: scroll,
      reverse: true,
      padding: const EdgeInsets.all(AppSpacing.md),
      children: turns.reversed.toList(),
    );
  }

  // The latest message and what follows it (pending text, live trace) form
  // the center: offset 0 is its top. Older turns, newest first, sit in the
  // sliver before it, which grows upward, so a late picture there never
  // moves the reply. The center is one box (not a lazy list): the composer
  // keeps its text and focus while scrolled away. A three-screen cache
  // keeps it in the semantics tree too: Flutter web's accessibility mode
  // types into that node, and a culled node came back empty.
  Widget _desk(List<Widget> turns, Widget panel) {
    final older = messages.isEmpty ? 0 : messages.length - 1;
    const pad = EdgeInsets.symmetric(horizontal: AppSpacing.md);
    return CustomScrollView(
      controller: scroll,
      center: _center,
      // scrollCacheExtent (its successor) does not compile on 3.47.9's
      // frontend: "Couldn't find constructor ScrollCacheExtent.viewport".
      // ignore: deprecated_member_use
      cacheExtent: 3200, // about three full-HD screens
      slivers: [
        SliverPadding(
          padding: pad.copyWith(top: AppSpacing.md),
          sliver: SliverList.list(
            children: turns.take(older).toList().reversed.toList(),
          ),
        ),
        SliverPadding(
          key: _center,
          padding: pad.copyWith(top: AppSpacing.md, bottom: AppSpacing.md),
          sliver: SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [...turns.skip(older), panel],
            ),
          ),
        ),
      ],
    );
  }

  static const Key _center = ValueKey('latest-turn');

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
