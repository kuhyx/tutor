/// Plan (curriculum §2/§8): the draft with editing (rename, reorder, add,
/// remove a module without cards, edit requires), a comment that asks the
/// tutor to redraft (`plan_revise`), and Approve. Approved plans show each
/// module's status and recall; a failed module can be retried.
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/plan/plan_ops.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/module_tile.dart';
import 'package:tutor/ui/plan_editor.dart';
import 'package:tutor/util/refresher.dart';

/// The Plan screen for one subject.
class PlanScreen extends StatefulWidget {
  /// Creates the screen.
  const new({required this.services, required this.subject, super.key});

  /// Services.
  final TutorServices services;

  /// Subject id.
  final String subject;

  @override
  State<PlanScreen> createState() => _PlanScreenState();
}

class _PlanScreenState extends State<PlanScreen> {
  late final RequestRunner _runner = RequestRunner(widget.services.relay);
  // The plan on screen stays put while a refetch runs; a change that would
  // replace a draft with unsaved edits waits behind a banner instead. Not
  // while our own request runs: the bump it causes can land before its
  // result, and the plan arriving then is the one just sent.
  late final _data = Refresher<SubjectData?>(
    () => widget.services.catalog.fetch(widget.subject),
    hold: (now, next) =>
        _editorDirty &&
        !_busy &&
        _editing(now) &&
        !samePlan(now?.plan, next?.plan),
  );
  late final StreamSubscription<int> _changes;
  final _comment = TextEditingController();
  bool _editorDirty = false;
  String? _editorKey;

  @override
  void initState() {
    super.initState();
    unawaited(_data.reload());
    // Live while visible: the worker bumps rev.catalog as modules generate.
    _changes = widget.services.rev.catalogChanges.listen(
      (_) => unawaited(_data.reload()),
    );
  }

  @override
  void dispose() {
    unawaited(_changes.cancel());
    unawaited(_runner.dispose());
    _data.dispose();
    _comment.dispose();
    super.dispose();
  }

  bool get _busy => switch (_runner.status.value) {
    RelayQueued() || RelayWorking() => true,
    _ => false,
  };

  static bool _editing(SubjectData? d) =>
      d != null &&
      d.plan?.status == 'draft' &&
      d.meta.status != SubjectStatus.failed &&
      d.meta.status != SubjectStatus.drafting;

  void _reload() => unawaited(_data.reload(force: true));

  void _onDirty(bool dirty) {
    _editorDirty = dirty;
    // Edits undone: a change that waited behind the banner can land now.
    if (!dirty) _data.applyPending();
  }

  Future<void> _send(RequestBody body) async {
    final status = await _runner.run(body);
    if (!mounted) return;
    if (status is RelayDone) _comment.clear();
    // Done or plan_conflict alike: the plan on screen may be stale now.
    if (status is RelayDone || status is RelayFailed) _reload();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Plan'),
      actions: [
        IconButton(
          tooltip: 'Reload',
          onPressed: _reload,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ListenableBuilder(
      listenable: _data,
      builder: (context, _) {
        final error = _data.error;
        if (!_data.hasData) {
          return error == null
              ? const Center(child: CircularProgressIndicator())
              : PageList(children: [Text('Could not load: $error')]);
        }
        final data = _data.data;
        if (data == null) {
          return const PageList(
            children: [Text('This subject does not exist (yet).')],
          );
        }
        return _body(context, data);
      },
    ),
  );

  Widget _body(BuildContext context, SubjectData data) {
    final plan = data.plan;
    final text = Theme.of(context).textTheme;
    final key = 'plan-${plan?.rev}-${_data.resets}';
    if (key != _editorKey) {
      // A new editor (new rev, or edits dropped): it starts clean.
      _editorKey = key;
      _editorDirty = false;
    }
    return PageList(
      children: [
        if (_data.hasPending)
          MaterialBanner(
            content: const Text('Plan changed — reload'),
            actions: [
              TextButton(
                onPressed: _data.applyPending,
                child: const Text('Reload plan'),
              ),
            ],
          ),
        if (_data.error != null) Text('Could not refresh: ${_data.error}'),
        Text(data.meta.title, style: text.headlineSmall),
        if (data.meta.goal.isNotEmpty) Text(data.meta.goal),
        const SizedBox(height: AppSpacing.sm),
        Pill(data.meta.status.wire.replaceAll('_', ' ')),
        RequestStatusLine(_runner),
        if (data.meta.status == SubjectStatus.failed)
          EmptyState(
            icon: Icons.error_outline,
            title: 'Drafting the plan failed',
            message: data.meta.error ?? 'Try again from Home.',
          )
        else if (plan == null || data.meta.status == SubjectStatus.drafting)
          const EmptyState(
            icon: Icons.hourglass_empty,
            title: 'The tutor is drafting the plan',
            message: 'It appears here by itself when the PC is done.',
          )
        else if (_editing(data)) ...[
          if (plan.notes.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(plan.notes, style: text.bodyMedium),
          ],
          PlanEditor(
            key: ValueKey(key),
            plan: plan,
            busy: _runner.status,
            onDirty: _onDirty,
            onSave: (modules) =>
                _send(RequestBody.planEdit(data.id, plan.rev, modules)),
            onApprove: () => _send(RequestBody.planApprove(data.id, plan.rev)),
          ),
          const SectionHeader('Ask for changes'),
          TextField(
            controller: _comment,
            minLines: 2,
            maxLines: 5,
            decoration: const InputDecoration(
              labelText: 'Comment (e.g. "less history, more maintenance")',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Align(
            alignment: Alignment.centerRight,
            child: OutlinedButton(
              onPressed: () {
                final c = _comment.text.trim();
                if (c.isNotEmpty) {
                  unawaited(
                    _send(RequestBody.planRevise(data.id, plan.rev, c)),
                  );
                }
              },
              child: const Text('Redraft with this comment'),
            ),
          ),
        ] else ...[
          const SectionHeader('Modules'),
          for (final m in plan.modules)
            ModuleProgressTile(
              module: m,
              onRetry: () => _send(RequestBody.planApprove(data.id, plan.rev)),
            ),
        ],
        if (plan != null && plan.history.isNotEmpty) ...[
          const SectionHeader('Revisions'),
          for (final h in plan.history) Text('rev ${h.rev}: ${h.comment}'),
        ],
      ],
    );
  }
}
