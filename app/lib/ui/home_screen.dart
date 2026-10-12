/// Home (shell): PC presence, due reviews, subjects. Full screens are B3b.
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/home/home_loader.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/relay/error_text.dart';

/// Home screen.
class HomeScreen extends StatefulWidget {
  /// Creates the screen.
  const new({required this.services, required this.onSignedOut, super.key});

  /// Services.
  final TutorServices services;

  /// Called after sign-out.
  final VoidCallback onSignedOut;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late Future<HomeSnapshot> _snapshot = widget.services.home.load();
  late final AppLifecycleListener _lifecycle;

  PresenceWatcher get _presence => widget.services.presence;

  @override
  void initState() {
    super.initState();
    // Stream presence only while visible (DOCS-contract §9 budget).
    _presence.start();
    _lifecycle = AppLifecycleListener(
      onShow: _presence.start,
      onHide: () => unawaited(_presence.stop()),
    );
  }

  @override
  void dispose() {
    _lifecycle.dispose();
    unawaited(_presence.stop());
    super.dispose();
  }

  void _refresh() => setState(() {
    _snapshot = widget.services.home.load();
  });

  Future<void> _signOut() async {
    await widget.services.auth.signOut();
    widget.onSignedOut();
  }

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
        IconButton(
          tooltip: 'Sign out',
          onPressed: _signOut,
          icon: const Icon(Icons.logout),
        ),
      ],
    ),
    body: FutureBuilder<HomeSnapshot>(
      future: _snapshot,
      builder: (context, snap) {
        // A refresh keeps the previous error/data in the snapshot while
        // waiting; show the spinner instead of a stale result.
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          return _Centered('Could not load: ${snap.error}');
        }
        return _HomeBody(snap.requireData);
      },
    ),
  );
}

class _HomeBody extends StatelessWidget {
  const new(this.data);

  final HomeSnapshot data;

  @override
  Widget build(BuildContext context) {
    final today = data.today;
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.md),
      children: [
        if (data.offline)
          const ListTile(
            leading: Icon(Icons.cloud_off),
            title: Text('Offline: showing the last synced catalog'),
          ),
        Card(
          child: ListTile(
            leading: const Icon(Icons.style),
            title: Text('${data.due} due for review'),
            subtitle: today == null
                ? null
                : Text(
                    'Today: ${today.creditedMinutes}/${today.target} min, '
                    'new ${today.newCards}/${today.newCap}',
                  ),
          ),
        ),
        const SectionHeader('Subjects'),
        if (data.subjects.isEmpty)
          const EmptyState(
            icon: Icons.lightbulb_outline,
            title: 'No subjects yet',
            message: 'New subjects arrive with the next app version.',
          ),
        for (final s in data.subjects)
          ListTile(
            title: Text(s.meta.title),
            subtitle: Text(s.meta.status.wire.replaceAll('_', ' ')),
          ),
      ],
    );
  }
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
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
          child: Center(child: Text(label)),
        ),
      );
    },
  );
}

class _Centered extends StatelessWidget {
  const new(this.text);

  final String text;

  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Text(text, textAlign: TextAlign.center),
    ),
  );
}
