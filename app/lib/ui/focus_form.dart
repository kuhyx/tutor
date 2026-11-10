import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/focus/focus_models.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/fit_layouts.dart';
import 'package:tutor/ui/focus_form_body.dart';
import 'package:tutor/ui/focus_gates.dart';
import 'package:tutor/ui/interview_draft.dart';
import 'package:tutor/ui/interview_prompts.dart';
import 'package:tutor/ui/numeric_date_picker.dart';

/// Creates or, given [edit], edits a focus project: dates, gates to turn
/// off, minutes, subjects.
class FocusFormScreen extends StatefulWidget {
  /// Creates the form over the PC's [status] (gates, subjects, today).
  const new({
    required this.services,
    required this.status,
    this.edit,
    this.prompts = const MaterialPrompts(),
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// The gate and subject lists, and today.
  final FocusStatus status;

  /// The project being edited; null creates a new one.
  final FocusProject? edit;

  /// The interview part's pickers.
  final InterviewPrompts prompts;

  @override
  State<FocusFormScreen> createState() => _FocusFormState();
}

String _iso(DateTime d) => d.toIso8601String().substring(0, 10);

class _FocusFormState extends State<FocusFormScreen> {
  late final RequestRunner _runner = RequestRunner(widget.services.relay);
  FocusProject? get _edit => widget.edit;
  late final _name = TextEditingController(text: _edit?.name);
  late final _daily = TextEditingController(
    text: '${_edit?.dailyMinutes ?? 120}',
  );
  late final _unlock = TextEditingController(
    text: '${_edit?.unlockMinutes ?? 30}',
  );
  late final _sites = TextEditingController(
    text: _edit?.sitePatterns.join(', '),
  );
  late final _workUrl = TextEditingController(text: _edit?.workUrl);
  final _draft = InterviewDraft();
  late final _off = <String>{...?_edit?.replaces};
  late final _linked = <String>{...?_edit?.subjects};
  late final DateTime _today = DateTime.parse(widget.status.day);
  late DateTime _start = DateTime.parse(_edit?.start ?? widget.status.day);
  late DateTime _end = _edit == null
      ? _start.add(const Duration(days: 3))
      : DateTime.parse(_edit!.end);
  // The registry refuses to move the start of a project that has begun.
  bool get _startLocked => _start.isBefore(_today);
  // An interview ends on its test day; the end date follows it.
  DateTime get _endDay => _draft.on ? _draft.testDay ?? _end : _end;

  @override
  void initState() {
    super.initState();
    _draft.addListener(_onDraft);
  }

  // The interview budget is 30 a day (DOCS-contract-focus.md); a plain
  // project keeps its 120 default, unless kuhy typed another number.
  void _onDraft() {
    final (from, to) = _draft.on ? ('120', '30') : ('30', '120');
    if (_daily.text == from) _daily.text = to;
    setState(() {});
  }

  @override
  void dispose() {
    for (final c in [_name, _daily, _unlock, _sites, _workUrl]) {
      c.dispose();
    }
    _draft.dispose();
    unawaited(_runner.dispose());
    super.dispose();
  }

  Future<void> _pick({required bool start}) async {
    final picked = await showNumericDatePicker(
      context: context,
      initialDate: start ? _start : _end,
      firstDate: _today,
      lastDate: _today.add(const Duration(days: 365)),
    );
    if (picked == null) return;
    setState(() => start ? _start = picked : _end = picked);
  }

  bool get _valid =>
      _name.text.trim().isNotEmpty &&
      (int.tryParse(_daily.text) ?? 0) > 0 &&
      int.tryParse(_unlock.text) != null &&
      isWorkUrl(_workUrl.text) &&
      !_endDay.isBefore(_start) &&
      (!_draft.on || _draft.valid);

  Future<void> _submit() async {
    final sites = _sites.text
        .split(',')
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty)
        .toList();
    final body = focusFormBody(
      id: _edit?.id,
      name: _name.text.trim(),
      start: _iso(_start),
      end: _iso(_endDay),
      replaces: _off.toList(),
      dailyMinutes: int.parse(_daily.text),
      unlockMinutes: int.parse(_unlock.text),
      subjects: _linked.toList(),
      sitePatterns: sites,
      workUrl: _workUrl.text.trim(),
    );
    final result = await _runner.run(_edit == null ? _draft.apply(body) : body);
    if (mounted && result is RelayDone) Navigator.of(context).pop(true);
  }

  void _edited(String _) => setState(() {});

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final status = widget.status;
    final fields = <Widget>[
      TextField(
        controller: _name,
        decoration: InputDecoration(labelText: l.projectName),
        onChanged: (_) => setState(() {}),
      ),
      const SizedBox(height: AppSpacing.md),
      Row(
        spacing: AppSpacing.md,
        children: [
          Expanded(
            child: DateField(
              l.startDate,
              _iso(_start),
              onTap: _startLocked ? null : () => _pick(start: true),
            ),
          ),
          Expanded(
            child: DateField(
              l.endDate,
              _iso(_endDay),
              onTap: _draft.on ? null : () => _pick(start: false),
            ),
          ),
        ],
      ),
      const SizedBox(height: AppSpacing.md),
      Row(
        spacing: AppSpacing.md,
        children: [
          Expanded(child: numberField(_daily, l.dailyMinutes, _edited)),
          Expanded(child: numberField(_unlock, l.unlockMinutes, _edited)),
        ],
      ),
      const SizedBox(height: AppSpacing.md),
      ...gateAndSubjectRows(
        context,
        status,
        off: _off,
        linked: _linked,
        changed: () => setState(() {}),
      ),
      const SizedBox(height: AppSpacing.md),
      TextField(
        controller: _sites,
        decoration: InputDecoration(labelText: l.sites),
      ),
      TextField(
        controller: _workUrl,
        keyboardType: TextInputType.url,
        decoration: InputDecoration(labelText: l.workUrl),
        onChanged: (_) => setState(() {}),
      ),
      if (_edit == null)
        ...interviewFields(context, _draft, widget.prompts, _today),
    ];
    final bar = <Widget>[
      RequestStatusLine(_runner),
      const SizedBox(height: AppSpacing.sm),
      RunnerBuilder(
        _runner,
        (_) => FilledButton(
          onPressed: _valid && _runner.canSend ? _submit : null,
          child: Text(_edit == null ? l.createProject : l.saveProject),
        ),
      ),
    ];
    return Scaffold(
      appBar: AppBar(title: Text(_edit == null ? l.newProject : l.editProject)),
      body: SafeArea(
        child: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: fitForm(
              context,
              fields: fields,
              bar: bar,
              wide: (all) => ListView(
                padding: const EdgeInsets.all(AppSpacing.md),
                keyboardDismissBehavior:
                    ScrollViewKeyboardDismissBehavior.onDrag,
                children: all,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
