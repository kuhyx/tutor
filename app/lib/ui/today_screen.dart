/// Today: the one current step of the day's plan and what to do with it.
/// Opens at app start when the server has a plan for today; Home is one
/// small icon away. Opening the app also starts the focus timer.
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/coach/coach_requests.dart';
import 'package:tutor/focus/focus_models.dart';
import 'package:tutor/focus/focus_send.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/mock/mock_entry.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/plan/today_plan.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/coach/coach_screen.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/fit_layouts.dart';
import 'package:tutor/ui/layout.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/sql/lesson_screen.dart';
import 'package:tutor/ui/today_parts.dart';

/// The Today screen.
class TodayScreen extends StatefulWidget {
  /// Creates the screen; [plan] is the one already fetched (or cached),
  /// [openHome] opens Home.
  const new({
    required this.services,
    required this.plan,
    required this.openHome,
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// The plan to show first; the screen refreshes it.
  final TodayPlan plan;

  /// Opens Home.
  final VoidCallback openHome;

  @override
  State<TodayScreen> createState() => _TodayScreenState();
}

class _TodayScreenState extends State<TodayScreen> {
  late final AppLifecycleListener _lifecycle;
  late TodayPlan _plan = widget.plan;
  bool _busy = false;

  TutorServices get _s => widget.services;

  @override
  void initState() {
    super.initState();
    _lifecycle = AppLifecycleListener(onResume: () => unawaited(_refresh()));
    unawaited(_refresh());
    unawaited(_startTimer());
  }

  @override
  void dispose() {
    _lifecycle.dispose();
    super.dispose();
  }

  // One runner per request: a runner tracks a single request in flight, and
  // the plan, the focus status and a Done tap overlap.
  Future<RelayStatus> _ask(RequestBody body) async {
    final runner = RequestRunner(_s.relay);
    try {
      return await runner.run(body);
    } finally {
      unawaited(runner.dispose());
    }
  }

  // Counting starts with the app: from the cached status at once, and again
  // from the PC's answer (the cache may be empty or stale).
  Future<void> _startTimer() async {
    await _s.focus.load();
    final cached = await cachedStatus(_s.kv);
    if (cached?.active != null) await _s.focus.ensureRunning();
    final result = await _ask(RequestBody.focusStatus());
    if (result is! RelayDone) return;
    await cacheStatus(_s.kv, result.data);
    if (parseStatus(result.data).active != null) {
      await _s.focus.ensureRunning();
    }
  }

  Future<void> _refresh() async {
    final result = await _ask(planToday());
    if (!mounted || result is! RelayDone) return;
    final fresh = TodayPlan.fromJson(result.data);
    if (fresh.steps.isEmpty) return;
    await cachePlan(_s.kv, result.data);
    if (mounted) setState(() => _plan = fresh);
  }

  Future<void> _done(PlanStep step) async {
    setState(() => _busy = true);
    final result = await _ask(planStepDone(step.id));
    if (!mounted) return;
    setState(() => _busy = false);
    if (result is RelayDone) {
      await cachePlan(_s.kv, result.data);
      if (mounted) setState(() => _plan = TodayPlan.fromJson(result.data));
    }
  }

  Future<void> _start(PlanStep step) async {
    await _open(step);
    if (mounted) unawaited(_refresh());
  }

  Future<void> _open(PlanStep step) => switch (step.kind) {
    StepKind.coach => Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => CoachScreen(
          services: _s,
          open: lcOpen(problem: step.target),
          title: step.title,
        ),
      ),
    ),
    StepKind.sqlLesson => Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => SqlLessonScreen(services: _s, topic: step.target),
      ),
    ),
    StepKind.sqlDrill => openSql(context, _s),
    StepKind.cards => openReview(
      context,
      _s,
      subject: step.target.isEmpty ? null : step.target,
      subjectTitle: step.title,
    ),
    StepKind.mock => openMock(context, _s),
    StepKind.note => Future<void>.value(),
  };

  @override
  Widget build(BuildContext context) {
    final step = _plan.current;
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.todayTitle),
        actions: [
          ListenableBuilder(
            listenable: _s.focus,
            builder: (_, _) => Padding(
              padding: const EdgeInsets.only(right: AppSpacing.sm),
              child: Center(
                child: Text(
                  _s.focus.isRunning
                      ? l10n.timerOn(_s.focus.counted.inMinutes)
                      : l10n.timerOff,
                  key: const ValueKey('today-timer'),
                ),
              ),
            ),
          ),
          IconButton(
            key: const ValueKey('today-home'),
            tooltip: l10n.homeTooltip,
            icon: const Icon(Icons.home_outlined),
            onPressed: widget.openHome,
          ),
        ],
      ),
      body: _body(context, step),
    );
  }

  Widget _body(BuildContext context, PlanStep? step) {
    final l10n = AppLocalizations.of(context);
    // Phone: Start and Done stay under the step on every page.
    final split = step != null && isCompact(context);
    final page = PageList(
      children: [
        PlanDots(_plan),
        const SizedBox(height: AppSpacing.lg),
        if (step == null)
          Text(l10n.allDone, key: const ValueKey('today-all-done'))
        else
          StepCard(
            step: step,
            number: _plan.steps.indexOf(step) + 1,
            total: _plan.steps.length,
            busy: _busy,
            actions: !split,
            onStart: () => unawaited(_start(step)),
            onDone: () => unawaited(_done(step)),
          ),
      ],
    );
    if (!split) return page;
    return FitSplit(
      body: page,
      bar: StepActions(
        step: step,
        busy: _busy,
        onStart: () => unawaited(_start(step)),
        onDone: () => unawaited(_done(step)),
      ),
    );
  }
}
