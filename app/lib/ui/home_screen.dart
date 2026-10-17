/// Home (curriculum §8): subjects with status/progress, a new subject from
/// free text, due reviews, PC presence, credited x/today's target, new x/10.
library;

import 'dart:async';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/home/home_loader.dart';
import 'package:tutor/home/remote_bits.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/display_size_dialog.dart';
import 'package:tutor/ui/home_body.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/util/refresher.dart';

/// Home screen.
class HomeScreen extends StatefulWidget {
  /// Creates the screen; [initialRoute] (fixture builds, deep links) is
  /// opened on top once Home is up.
  const new({
    required this.services,
    required this.onSignedOut,
    this.initialRoute,
    this.allowSignOut = !kIsWeb,
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// Called after sign-out.
  final VoidCallback onSignedOut;

  /// A route such as `/plan/car` to open first.
  final String? initialRoute;

  /// Off on the desktop (web) build: it signs in from the PC's server once
  /// per server start, so a sign-out there could not be undone in-app.
  final bool allowSignOut;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // The last snapshot stays on screen while a refresh runs (no flash).
  late final _snapshot = Refresher<HomeSnapshot>(widget.services.home.load);
  late final StreamSubscription<int> _changes;
  late final AppLifecycleListener _lifecycle;
  late final RequestRunner _runner = RequestRunner(widget.services.relay);

  TutorServices get _s => widget.services;
  PresenceWatcher get _presence => _s.presence;

  @override
  void initState() {
    super.initState();
    // Stream presence only while visible (DOCS-contract §9 budget).
    unawaited(_snapshot.reload());
    // Only while Home is on top: returning to it refreshes anyway (_back),
    // and a reload here re-GETs every subject once rev.catalog moved.
    _changes = _s.rev.catalogChanges.listen((_) {
      if (mounted && (ModalRoute.of(context)?.isCurrent ?? true)) _refresh();
    });
    _presence.start();
    _lifecycle = AppLifecycleListener(
      onShow: _presence.start,
      onHide: () => unawaited(_presence.stop()),
    );
    final route = widget.initialRoute;
    if (route != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) unawaited(openRoute(context, _s, route).then(_back));
      });
    }
  }

  @override
  void dispose() {
    _lifecycle.dispose();
    unawaited(_changes.cancel());
    _snapshot.dispose();
    unawaited(_presence.stop());
    unawaited(_runner.dispose());
    super.dispose();
  }

  void _refresh() => unawaited(_snapshot.reload());

  // Back on Home from any screen: counters may have moved.
  void _back(Object? _) {
    if (mounted) _refresh();
  }

  Future<void> _signOut() async {
    await _s.auth.signOut();
    widget.onSignedOut();
  }

  Future<void> _newSubject(String text) async {
    final status = await _runner.run(RequestBody.subjectNew(text));
    if (!mounted || status is! RelayDone) return;
    final subject = status.data['subject'];
    _refresh();
    if (subject is String) await openPlan(context, _s, subject).then(_back);
  }

  Future<void> _finish(String subject, {required bool goDeeper}) async {
    final status = await _runner.run(
      RequestBody.subjectFinish(subject, goDeeper: goDeeper),
    );
    if (!mounted || status is! RelayDone) return;
    _refresh();
    if (goDeeper) await openPlan(context, _s, subject).then(_back);
  }

  Future<void> _pick(String subject) async {
    try {
      await setCurrentSubject(_s.client, subject);
    } on Object catch (error) {
      // `on Object`: shown, never swallowed; the pick is simply not saved.
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Not saved: $error')));
      }
      return;
    }
    _refresh();
  }

  Future<void> _go(Future<void> Function() open) => open().then(_back);

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Tutor'),
      actions: [
        _PresenceChip(_presence.state),
        IconButton(
          tooltip: 'Refresh',
          onPressed: _refresh,
          icon: const Icon(Icons.refresh),
        ),
        PopupMenuButton<String>(
          tooltip: 'More',
          onSelected: (v) => switch (v) {
            'history' => _go(() => openHistory(context, _s)),
            'progress' => _go(() => openProgress(context, _s)),
            'editor' => _go(() => openEditor(context, _s)),
            'report' => showReport(context, _s, route: '/'),
            'display' => showDisplaySize(context),
            _ => _signOut(),
          },
          itemBuilder: (_) => [
            const PopupMenuItem(value: 'history', child: Text('History')),
            const PopupMenuItem(value: 'progress', child: Text('Progress')),
            const PopupMenuItem(value: 'editor', child: Text('Edit cards')),
            const PopupMenuItem(value: 'display', child: Text('Display size')),
            const PopupMenuItem(
              value: 'report',
              child: Text('Report a problem'),
            ),
            if (widget.allowSignOut)
              const PopupMenuItem(value: 'signout', child: Text('Sign out')),
          ],
        ),
      ],
    ),
    body: ListenableBuilder(
      listenable: _snapshot,
      builder: (context, _) {
        // A failed load shows its error (the loader already falls back to
        // the cache when offline, so what is left is worth reading).
        final error = _snapshot.error;
        if (error != null) {
          return PageList(children: [Text('Could not load: $error')]);
        }
        if (!_snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        return HomeBody(
          data: _snapshot.data,
          presence: _presence.state,
          runner: _runner,
          onReview: () => _go(() => openReview(context, _s)),
          onDrill: () => _go(() => openReview(context, _s, drill: true)),
          onReviewModule: (m) => _go(() => openReview(context, _s, module: m)),
          onSession: (e) => _go(() => openSession(context, _s, entry: e)),
          onPlan: (id) => _go(() => openPlan(context, _s, id)),
          onEdit: (id) => _go(() => openEditor(context, _s, subject: id)),
          onPick: _pick,
          onNewSubject: _newSubject,
          onFinish: _finish,
        );
      },
    ),
  );
}

class _PresenceChip extends StatelessWidget {
  const new(this.state);

  final ValueNotifier<PcPresence> state;

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<PcPresence>(
    valueListenable: state,
    builder: (context, value, _) {
      final (label, tip) = switch (value) {
        PcPresence.checking => ('PC: checking', 'Waiting for a heartbeat'),
        PcPresence.online => ('PC online', 'Replies come from the PC'),
        PcPresence.offline => ('PC offline', pcOfflineText),
      };
      return Tooltip(
        message: tip,
        child: Center(child: Pill(label, warn: value == PcPresence.offline)),
      );
    },
  );
}
