import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/focus/focus_models.dart';
import 'package:tutor/focus/focus_send.dart';
import 'package:tutor/focus/focus_timer.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/review/review_session.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/focus_form.dart';
import 'package:tutor/ui/focus_gates.dart';
import 'package:tutor/ui/focus_ring.dart';
import 'package:tutor/ui/review_answer.dart';

/// The most overtime the server banks for the next day (`focus_project`).
const int _bankCap = 60;

/// The focus project: today's ring, the timer and its check-in: one recall
/// card inline (in the ring's place), or the old "Still working" tap.
class FocusScreen extends StatefulWidget {
  /// Creates the screen; [autoStart] (the `/focus?start=1` deep link)
  /// starts the timer once, unless it is already running.
  const new({required this.services, this.autoStart = false, super.key});

  /// Services.
  final TutorServices services;

  /// Start the timer when the project is known and it is not running.
  final bool autoStart;

  @override
  State<FocusScreen> createState() => _FocusScreenState();
}

class _FocusScreenState extends State<FocusScreen> {
  late final RequestRunner _runner = RequestRunner(_s.relay);
  FocusStatus? _status;
  int _countedAtLoad = 0;
  bool _autoStarted = false;
  ReviewSession? _card; // the check-in card's one-card review run

  TutorServices get _s => widget.services;
  FocusTimer get _timer => _s.focus;

  @override
  void initState() {
    super.initState();
    _timer.attach();
    unawaited(_timer.load());
    unawaited(_load());
  }

  @override
  void dispose() {
    _timer.detach();
    unawaited(_runner.dispose());
    _card?.dispose();
    super.dispose();
  }

  // The review run of the timer's check-in card (one per pick); its rating
  // is an ordinary review tagged `checkin`, and its time is the beat's.
  ReviewSession? _cardRun() {
    // A replaced run is left to the GC, not disposed: its rating may still
    // be finishing (it notifies after the timer has moved on).
    final item = _timer.checkinCard;
    if (item == null) return _card = null;
    final run = _card;
    if (run != null && run.items.single == item) return run;
    return _card = ReviewSession(
      items: [item],
      events: _s.events,
      src: checkinSource,
      onRated: (at) => unawaited(_timer.cardRated(at)),
      now: () => DateTime.fromMillisecondsSinceEpoch(_timer.nowMs()),
    );
  }

  Future<void> _load() async {
    final cached = await cachedStatus(_s.kv);
    if (mounted && cached != null && _status == null) {
      setState(() => _status = cached);
      await _autoStart();
    }
    await _timer.flush();
    final result = await _runner.run(RequestBody.focusStatus());
    if (!mounted || result is! RelayDone) return;
    await cacheStatus(_s.kv, result.data);
    setState(() {
      _status = parseStatus(result.data);
      _countedAtLoad = _timer.counted.inMinutes;
    });
    await _autoStart();
  }

  // Once, and only with a project to count for: the link must not start a
  // timer against nothing, nor reset a run that is already live.
  Future<void> _autoStart() async {
    if (!widget.autoStart || _autoStarted || _status?.active == null) return;
    _autoStarted = true;
    await _timer.ensureRunning();
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

  Future<void> _form({FocusProject? edit}) async {
    final status = _status;
    if (status == null) return;
    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) =>
            FocusFormScreen(services: _s, status: status, edit: edit),
      ),
    );
    if (saved ?? false) await _load();
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
            onPressed: _form,
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
    // Real minutes, never capped (121/120): the overtime banks for tomorrow.
    final shown = project.minutes + live;
    final banked = (shown - project.dailyMinutes).clamp(0, _bankCap);
    final card = _cardRun();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(project.name, style: text.headlineSmall),
        Text(l.daysLeft(project.daysLeft), style: text.bodyMedium),
        Expanded(
          child: card != null
              ? _checkinCard(card)
              : Center(
                  child: FocusRing(
                    minutes: shown,
                    goal: project.dailyMinutes,
                    banked: banked > 0 ? l.banked(banked) : null,
                    caption: running ? focusClock(_timer.counted) : null,
                  ),
                ),
        ),
        FocusGates(status),
        const SizedBox(height: AppSpacing.sm),
        if (_timer.wantsTap)
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
        // Wraps at a large font instead of overflowing.
        Wrap(
          alignment: WrapAlignment.spaceBetween,
          children: [
            TextButton(onPressed: _form, child: Text(l.newProject)),
            TextButton(
              onPressed: () => _form(edit: project),
              child: Text(l.editProject),
            ),
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

  // Review's own card UI, without Back and Flag: the card leaves on its
  // rating. Scrolls, as a revealed card can outgrow a phone screen.
  Widget _checkinCard(ReviewSession run) => ListenableBuilder(
    listenable: run,
    builder: (context, _) {
      final item = run.current;
      if (item == null) return const SizedBox.shrink();
      return SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            CardFace(item.card, revealed: run.revealed),
            const SizedBox(height: AppSpacing.sm),
            AnswerBar(run, onFlag: null),
          ],
        ),
      );
    },
  );
}
