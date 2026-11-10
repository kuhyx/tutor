import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/focus/focus_models.dart';
import 'package:tutor/focus/focus_send.dart';
import 'package:tutor/focus/focus_timer.dart';
import 'package:tutor/focus/screenshot_picker.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/focus_checkin_view.dart';
import 'package:tutor/ui/focus_form.dart';
import 'package:tutor/ui/focus_gates.dart';
import 'package:tutor/ui/focus_parts.dart';
import 'package:tutor/ui/focus_ring.dart';
import 'package:tutor/ui/interview_panel.dart';
import 'package:tutor/ui/interview_prompts.dart';
import 'package:tutor/widgets/content_text.dart';

/// The most overtime the server banks for the next day (`focus_project`).
const int _bankCap = 60;

/// The focus project: today's ring, the timer and its check-in: one recall
/// card inline (in the ring's place), or the old "Still working" tap.
class FocusScreen extends StatefulWidget {
  /// Creates the screen; [autoStart] (the `/focus?start=1` deep link)
  /// starts the timer once, unless it is already running.
  const new({
    required this.services,
    this.autoStart = false,
    this.pickImage = pickScreenshot,
    this.prompts = const MaterialPrompts(),
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// Start the timer when the project is known and it is not running.
  final bool autoStart;

  /// Picks the rules screenshot of an interview project.
  final PickImage pickImage;

  /// The questions an interview milestone asks.
  final InterviewPrompts prompts;

  @override
  State<FocusScreen> createState() => _FocusScreenState();
}

class _FocusScreenState extends State<FocusScreen> {
  late final RequestRunner _runner = RequestRunner(_s.relay);
  FocusStatus? _status;
  bool _autoStarted = false;
  late final CheckinCardRun _checkin = CheckinCardRun(
    _s,
    (work) => unawaited(_then(work)),
  );

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
    _checkin.dispose();
    super.dispose();
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
      await _timer.start();
      await _load();
    }
  }

  // A tap or an answer changed what the server counts: ask it again.
  Future<void> _then(Future<void> tap) async {
    await tap;
    if (mounted) await _load();
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
    if (project == null) return NoProject(onNew: _form);
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
    // Real minutes, never capped (121/120): the overtime banks for tomorrow.
    // Server figures only: the client clock never moves the ring.
    final shown = project.minutes;
    final banked = (shown - project.dailyMinutes).clamp(0, _bankCap);
    final card = _checkin.run();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ContentText(project.name, style: text.headlineSmall),
        Text(l.daysLeft(project.daysLeft), style: text.bodyMedium),
        Expanded(
          child: card != null
              ? CheckinCardRun.view(card)
              : Center(
                  child: FocusRing(
                    minutes: shown,
                    goal: project.dailyMinutes,
                    banked: banked > 0 ? l.banked(banked) : null,
                    caption: running ? focusClock(_timer.counted) : null,
                  ),
                ),
        ),
        ...unbackedRow(project.unbackedMinutes),
        if (project.interview != null)
          InterviewPanel(
            services: _s,
            project: project,
            today: status.day,
            minutes: shown,
            pickImage: widget.pickImage,
            prompts: widget.prompts,
            onChanged: (i) =>
                setState(() => _status = statusWithInterview(status, i)),
          ),
        FocusGates(status),
        const SizedBox(height: AppSpacing.sm),
        if (_timer.wantsTap)
          FilledButton.icon(
            onPressed: () => _then(_timer.checkin()),
            icon: const Icon(Icons.check),
            label: Text(l.stillWorking),
          ),
        if (_timer.isLapsed)
          Text(
            l.missedCheckin,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        const SizedBox(height: AppSpacing.sm),
        StartStopButton(running: running, onPressed: _toggle),
        ProjectActions(
          onNew: _form,
          onEdit: () => _form(edit: project),
          onEnd: () => _end(project),
        ),
        RequestStatusLine(_runner, queuedText: l.queued),
      ],
    );
  }
}
