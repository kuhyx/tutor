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
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/plan_editor.dart';

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
  late Future<SubjectData?> _data = _load();
  final _comment = TextEditingController();

  Future<SubjectData?> _load() => widget.services.catalog.fetch(widget.subject);

  @override
  void dispose() {
    unawaited(_runner.dispose());
    _comment.dispose();
    super.dispose();
  }

  void _reload() => setState(() => _data = _load());

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
    body: FutureBuilder<SubjectData?>(
      future: _data,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          return PageList(children: [Text('Could not load: ${snap.error}')]);
        }
        final data = snap.data;
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
    final draft = plan != null && plan.status == 'draft';
    return PageList(
      children: [
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
            message: 'It appears here when the PC is done. Reload to check.',
          )
        else if (draft) ...[
          if (plan.notes.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(plan.notes, style: text.bodyMedium),
          ],
          PlanEditor(
            key: ValueKey('plan-${plan.rev}'),
            plan: plan,
            busy: _runner.status,
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
            _ModuleProgressTile(
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

class _ModuleProgressTile extends StatelessWidget {
  const new({required this.module, required this.onRetry});

  final Module module;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final m = module;
    final failed = m.status == ModuleStatus.failed;
    return Card(
      child: ListTile(
        title: Text(m.title),
        subtitle: Text(
          [
            m.status.name,
            if (m.cards > 0) '${m.cards} cards',
            'recall ${(m.recall * 100).round()}%',
            if (failed && m.error != null) m.error!,
          ].join(' · '),
        ),
        trailing: failed
            ? TextButton(onPressed: onRetry, child: const Text('Retry'))
            : null,
      ),
    );
  }
}
