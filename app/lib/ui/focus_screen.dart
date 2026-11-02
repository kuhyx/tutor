import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/focus/focus_models.dart';
import 'package:tutor/focus/focus_send.dart';
import 'package:tutor/focus/focus_timer.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/focus_form.dart';
import 'package:tutor/ui/focus_ring.dart';

/// The focus project: today's ring, the timer and its check-in.
class FocusScreen extends StatefulWidget {
  /// Creates the screen.
  const new({required this.services, super.key});

  /// Services.
  final TutorServices services;

  @override
  State<FocusScreen> createState() => _FocusScreenState();
}

class _FocusScreenState extends State<FocusScreen> {
  late final RequestRunner _runner = RequestRunner(_s.relay);
  FocusStatus? _status;
  int _countedAtLoad = 0;

  TutorServices get _s => widget.services;
  FocusTimer get _timer => _s.focus;

  @override
  void initState() {
    super.initState();
    unawaited(_timer.load());
    unawaited(_load());
  }

  @override
  void dispose() {
    unawaited(_runner.dispose());
    super.dispose();
  }

  Future<void> _load() async {
    final cached = await cachedStatus(_s.kv);
    if (mounted && cached != null && _status == null) {
      setState(() => _status = cached);
    }
    await _timer.flush();
    final result = await _runner.run(RequestBody.focusStatus());
    if (!mounted || result is! RelayDone) return;
    await cacheStatus(_s.kv, result.data);
    setState(() {
      _status = parseStatus(result.data);
      _countedAtLoad = _timer.counted.inMinutes;
    });
  }

  Future<void> _toggle() async {
    if (_timer.isRunning) {
      await _timer.stop();
      await _load();
    } else {
      _countedAtLoad = 0;
      await _timer.start();
    }
  }

  Future<void> _new() async {
    final status = _status;
    if (status == null) return;
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => FocusFormScreen(services: _s, status: status),
      ),
    );
    if (created ?? false) await _load();
  }

  Future<void> _end(FocusProject project) async {
    final l = AppLocalizations.of(context);
    final sure = await confirmDestructive(
      context,
      title: l.endProject,
      message: project.name,
      confirmLabel: l.endProject,
    );
    if (!sure) return;
    final result = await _runner.run(RequestBody.focusEnd(project.id));
    if (result is RelayDone) await _load();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(l.focus)),
      body: SafeArea(
        child: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: ListenableBuilder(
                listenable: _timer,
                builder: (context, _) => _body(context, l),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _body(BuildContext context, AppLocalizations l) {
    final status = _status;
    final project = status?.active;
    if (status == null) {
      return Column(
        children: [Expanded(child: Center(child: RequestStatusLine(_runner)))],
      );
    }
    if (project == null) {
      return Column(
        children: [
          Expanded(
            child: EmptyState(
              icon: Icons.center_focus_strong_outlined,
              title: l.noProject,
              message: '',
            ),
          ),
          FilledButton.icon(
            onPressed: _new,
            icon: const Icon(Icons.add),
            label: Text(l.newProject),
          ),
        ],
      );
    }
    return _project(context, l, status, project);
  }

  Widget _project(
    BuildContext context,
    AppLocalizations l,
    FocusStatus status,
    FocusProject project,
  ) {
    final text = Theme.of(context).textTheme;
    final running = _timer.isRunning;
    final lapsed = _timer.isLapsed;
    final live = (_timer.counted.inMinutes - _countedAtLoad).clamp(0, 999);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(project.name, style: text.headlineSmall),
        Text(l.daysLeft(project.daysLeft), style: text.bodyMedium),
        Expanded(
          child: Center(
            child: FocusRing(
              minutes: project.minutes + live,
              goal: project.dailyMinutes,
              caption: running ? _clock(_timer.counted) : null,
            ),
          ),
        ),
        _Gates(status),
        const SizedBox(height: AppSpacing.sm),
        if (_timer.checkinDue)
          FilledButton.icon(
            onPressed: _timer.checkin,
            icon: const Icon(Icons.check),
            label: Text(l.stillWorking),
          ),
        if (lapsed)
          Text(
            l.missedCheckin,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        const SizedBox(height: AppSpacing.sm),
        SizedBox(
          height: 72,
          child: FilledButton.icon(
            onPressed: _toggle,
            icon: Icon(running ? Icons.stop : Icons.play_arrow),
            label: Text(running ? l.stop : l.start),
          ),
        ),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            TextButton(onPressed: _new, child: Text(l.newProject)),
            TextButton(
              onPressed: () => _end(project),
              child: Text(l.endProject),
            ),
          ],
        ),
        RequestStatusLine(_runner, queuedText: l.queued),
      ],
    );
  }
}

String _clock(Duration d) {
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(d.inMinutes)}:${two(d.inSeconds % 60)}';
}

class _Gates extends StatelessWidget {
  const new(this.status);

  final FocusStatus status;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Wrap(
      spacing: AppSpacing.sm,
      runSpacing: AppSpacing.xs,
      alignment: WrapAlignment.center,
      children: [
        for (final label in gateLabels(status, off: true))
          Chip(
            avatar: const Icon(Icons.block, size: 16),
            label: Text(label),
            side: BorderSide(color: scheme.outlineVariant),
          ),
        for (final label in gateLabels(status, off: false))
          Chip(avatar: const Icon(Icons.check, size: 16), label: Text(label)),
      ],
    );
  }
}
