/// The interview part of the Focus screen: the milestone icon row, and what a
/// tap on each icon asks for and sends (DOCS-contract-focus.md).
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/focus/evidence_upload.dart';
import 'package:tutor/focus/focus_models.dart';
import 'package:tutor/focus/interview_actions.dart';
import 'package:tutor/focus/interview_models.dart';
import 'package:tutor/focus/screenshot_picker.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/interview_prompts.dart';
import 'package:tutor/ui/interview_row.dart';

/// Milestone icons for an interview [project]; a successful action hands the
/// redrawn state to [onChanged].
class InterviewPanel extends StatefulWidget {
  /// Creates the panel. [today] is `focus_status`'s day; [minutes] the
  /// minutes counted today (the clock icon).
  const new({
    required this.services,
    required this.project,
    required this.today,
    required this.minutes,
    required this.onChanged,
    required this.pickImage,
    required this.prompts,
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// The interview project (its `interview` part is set).
  final FocusProject project;

  /// Today, `YYYY-MM-DD`.
  final String today;

  /// Minutes counted today, live.
  final int minutes;

  /// Called with the state a result redrew.
  final ValueChanged<InterviewState> onChanged;

  /// Picks the rules screenshot.
  final PickImage pickImage;

  /// The questions.
  final InterviewPrompts prompts;

  @override
  State<InterviewPanel> createState() => _InterviewPanelState();
}

class _InterviewPanelState extends State<InterviewPanel> {
  late final RequestRunner _runner = RequestRunner(widget.services.relay);
  late final InterviewActions _actions = InterviewActions(
    runner: _runner,
    uploader: EvidenceUploader(
      client: widget.services.client,
      ulid: widget.services.relay.ulid,
    ),
    projectId: widget.project.id,
  );
  String? _error;
  String? _errorKind;
  bool _busy = false;
  bool _slotEntered = false; // entered here, not yet confirmed

  InterviewState get _state => widget.project.interview!;

  @override
  void dispose() {
    unawaited(_runner.dispose());
    super.dispose();
  }

  List<Milestone> _of(MilestoneGroup g) => [
    for (final m in _state.milestones)
      if (groupOf(m.id) == g) m,
  ];

  Light _light(Slot s) => switch (s) {
    Slot.clock =>
      widget.minutes >= widget.project.dailyMinutes ? Light.green : Light.grey,
    Slot.rules => groupLight(_of(MilestoneGroup.rules)),
    Slot.trip => groupLight(_of(MilestoneGroup.tripAsk)),
    Slot.phone => groupLight(_of(MilestoneGroup.phone)),
    Slot.mock => groupLight(_of(MilestoneGroup.mock)),
    Slot.slot => groupLight(_of(MilestoneGroup.slot)),
  };

  DateTime get _first => DateTime.parse(widget.today);
  DateTime get _last {
    final t = _state.testAt;
    return t == null
        ? _first.add(const Duration(days: 365))
        : DateTime(t.year, t.month, t.day);
  }

  VoidCallback? _handler(Slot s) => switch (s) {
    Slot.clock => null,
    Slot.rules => _rules,
    Slot.trip => _trip,
    Slot.phone => _phone,
    Slot.mock => _mock,
    Slot.slot => _slot,
  };

  // Runs one action; a result redraws, a failure shows (never swallowed).
  Future<bool> _run(Future<RelayStatus> Function() act) async {
    setState(() {
      _error = null;
      _errorKind = null;
      _busy = true;
    });
    final result = await act();
    if (!mounted) return false;
    setState(() {
      _busy = false;
      _error = failureText(result);
      _errorKind = result is RelayFailed ? result.kind : null;
    });
    if (result is RelayDone && result.data.containsKey('milestones')) {
      widget.onChanged(applyBlock(_state, result.data));
    }
    return result is RelayDone;
  }

  Future<void> _rules() async {
    final m = actionable(_of(MilestoneGroup.rules));
    if (m == null || _busy) return;
    final bytes = await widget.pickImage();
    if (bytes == null || !mounted) return;
    await _run(() => _actions.file(m.id, bytes));
  }

  Future<void> _trip() async {
    if (_busy) return;
    final yes = await widget.prompts.askTrip(context);
    if (yes == null || !mounted) return;
    if (yes) {
      final r = await widget.prompts.pickRange(
        context,
        first: _first,
        last: _last,
      );
      if (r == null) return;
      await _run(() => _actions.trip(r.start, r.end));
      return;
    }
    final open = actionable(_of(MilestoneGroup.tripAsk));
    final saturday = open == null ? null : argOf(open.id);
    if (saturday != null) await _run(() => _actions.noTrip(saturday));
  }

  Future<void> _phone() async {
    final m = actionable(_of(MilestoneGroup.phone));
    if (m == null || _busy) return;
    if (await widget.prompts.confirm(context) ?? false) {
      await _run(() => _actions.tap(m.id));
    }
  }

  Future<void> _mock() async {
    final m = actionable(_of(MilestoneGroup.mock));
    if (m == null || _busy) return;
    final score = await widget.prompts.askScore(context);
    if (score != null) await _run(() => _actions.score(m.id, score));
  }

  Future<void> _slot() async {
    if (actionable(_of(MilestoneGroup.slot)) == null || _busy) return;
    if (_slotEntered) {
      final again = await widget.prompts.confirm(context);
      if (again == null || !mounted) return;
      if (again) {
        await _confirmSlot();
        return;
      }
    }
    final at = await widget.prompts.pickDateTime(
      context,
      first: _first,
      last: _last,
    );
    if (at == null || !mounted) return;
    if (!await _run(() => _actions.slot(at)) || !mounted) return;
    _slotEntered = true;
    if (await widget.prompts.confirm(context) ?? false) await _confirmSlot();
  }

  Future<void> _confirmSlot() async {
    if (await _run(_actions.slotConfirm)) _slotEntered = false;
  }

  @override
  Widget build(BuildContext context) {
    final error = _error;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          key: const ValueKey('interview-row'),
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            for (final s in Slot.values)
              MilestoneIcon(s, _light(s), onTap: _handler(s)),
          ],
        ),
        if (_busy)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: AppSpacing.xs),
            child: LinearProgressIndicator(),
          ),
        if (error != null)
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.xs),
            child: InterviewError(
              error,
              kind: _errorKind,
              key: const ValueKey('interview-error'),
            ),
          ),
      ],
    );
  }
}
