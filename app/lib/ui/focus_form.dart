import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/focus/focus_models.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';

/// Creates a focus project: dates, gates to turn off, minutes, subjects.
class FocusFormScreen extends StatefulWidget {
  /// Creates the form over the PC's [status] (gates, subjects, today).
  const new({required this.services, required this.status, super.key});

  /// Services.
  final TutorServices services;

  /// The gate and subject lists, and today.
  final FocusStatus status;

  @override
  State<FocusFormScreen> createState() => _FocusFormState();
}

String _iso(DateTime d) => d.toIso8601String().substring(0, 10);

class _FocusFormState extends State<FocusFormScreen> {
  late final RequestRunner _runner = RequestRunner(widget.services.relay);
  final _name = TextEditingController();
  final _daily = TextEditingController(text: '120');
  final _unlock = TextEditingController(text: '30');
  final _sites = TextEditingController();
  final _off = <String>{};
  final _linked = <String>{};
  late DateTime _start = DateTime.parse(widget.status.day);
  late DateTime _end = _start.add(const Duration(days: 3));

  @override
  void dispose() {
    for (final c in [_name, _daily, _unlock, _sites]) {
      c.dispose();
    }
    unawaited(_runner.dispose());
    super.dispose();
  }

  Future<void> _pick({required bool start}) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: start ? _start : _end,
      firstDate: DateTime.parse(widget.status.day),
      lastDate: DateTime.parse(widget.status.day)
          .add(const Duration(days: 365)),
    );
    if (picked == null) return;
    setState(() => start ? _start = picked : _end = picked);
  }

  void _toggleGate(String id, {required bool on}) =>
      on ? _off.add(id) : _off.remove(id);

  bool get _valid =>
      _name.text.trim().isNotEmpty &&
      (int.tryParse(_daily.text) ?? 0) > 0 &&
      int.tryParse(_unlock.text) != null &&
      !_end.isBefore(_start);

  Future<void> _create() async {
    final sites = _sites.text
        .split(',')
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty)
        .toList();
    final result = await _runner.run(
      RequestBody.focusCreate(
        name: _name.text.trim(),
        start: _iso(_start),
        end: _iso(_end),
        replaces: _off.toList(),
        dailyMinutes: int.parse(_daily.text),
        unlockMinutes: int.parse(_unlock.text),
        subjects: _linked.toList(),
        sitePatterns: sites,
      ),
    );
    if (mounted && result is RelayDone) Navigator.of(context).pop(true);
  }

  Widget _number(TextEditingController c, String label) => TextField(
    controller: c,
    keyboardType: TextInputType.number,
    decoration: InputDecoration(labelText: label),
    onChanged: (_) => setState(() {}),
  );

  Widget _date(String label, DateTime value, {required bool start}) => Expanded(
    child: InkWell(
      onTap: () => _pick(start: start),
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          suffixIcon: const Icon(Icons.event),
        ),
        child: Text(_iso(value)),
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final status = widget.status;
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: Text(l.newProject)),
      body: SafeArea(
        child: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: ListView(
              padding: const EdgeInsets.all(AppSpacing.md),
              keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
              children: [
                TextField(
                  controller: _name,
                  decoration: InputDecoration(labelText: l.projectName),
                  onChanged: (_) => setState(() {}),
                ),
                const SizedBox(height: AppSpacing.md),
                Row(
                  spacing: AppSpacing.md,
                  children: [
                    _date(l.startDate, _start, start: true),
                    _date(l.endDate, _end, start: false),
                  ],
                ),
                const SizedBox(height: AppSpacing.md),
                Row(
                  spacing: AppSpacing.md,
                  children: [
                    Expanded(child: _number(_daily, l.dailyMinutes)),
                    Expanded(child: _number(_unlock, l.unlockMinutes)),
                  ],
                ),
                const SizedBox(height: AppSpacing.md),
                Text(l.gatesOff, style: text.titleSmall),
                for (final g in status.gates)
                  CheckboxListTile(
                    dense: true,
                    value: _off.contains(g.id),
                    onChanged: g.replaceable
                        ? (v) =>
                              setState(() => _toggleGate(g.id, on: v ?? false))
                        : null,
                    title: Text(g.label),
                    subtitle: g.replaceable ? null : Text(l.gateKept),
                  ),
                if (status.subjects.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Text(l.subjects, style: text.titleSmall),
                  Wrap(
                    spacing: AppSpacing.sm,
                    children: [
                      for (final s in status.subjects)
                        FilterChip(
                          label: Text(s.title),
                          selected: _linked.contains(s.id),
                          onSelected: (v) => setState(
                            () => v ? _linked.add(s.id) : _linked.remove(s.id),
                          ),
                        ),
                    ],
                  ),
                ],
                const SizedBox(height: AppSpacing.md),
                TextField(
                  controller: _sites,
                  decoration: InputDecoration(labelText: l.sites),
                ),
                RequestStatusLine(_runner),
                const SizedBox(height: AppSpacing.sm),
                RunnerBuilder(
                  _runner,
                  (_) => FilledButton(
                    onPressed: _valid && _runner.canSend ? _create : null,
                    child: Text(l.createProject),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
