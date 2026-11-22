/// Opens the routes a later window hands to this one (C4, `deep_link_web`).
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/ui/deep_link.dart';
import 'package:tutor/ui/nav.dart';

/// Opens each route of [routes] over whatever is on screen, as a deep link
/// would; [child] is shown as is. Only while this is mounted does the window
/// take a route, so one still loading lets the new window boot instead.
class RouteInbox extends StatefulWidget {
  /// Creates the inbox; [routes] defaults to the windows' [handedRoutes].
  const new({
    required this.services,
    required this.child,
    this.routes,
    super.key,
  });

  /// What a route opens with.
  final TutorServices services;

  /// The screen under the opened routes.
  final Widget child;

  /// The routes to open (tests inject them).
  final Stream<String>? routes;

  @override
  State<RouteInbox> createState() => _RouteInboxState();
}

class _RouteInboxState extends State<RouteInbox> {
  late final StreamSubscription<String> _sub;

  @override
  void initState() {
    super.initState();
    // Listening now is what lets this window take a route (deep_link_web).
    _sub = (widget.routes ?? handedRoutes).listen((route) {
      if (mounted) unawaited(openRoute(context, widget.services, route));
    });
  }

  @override
  void dispose() {
    unawaited(_sub.cancel());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
