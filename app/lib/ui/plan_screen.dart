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
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/plan/plan_ops.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/learn_bits.dart';
import 'package:tutor/ui/learn_rows.dart';
import 'package:tutor/ui/learn_tiles.dart';
import 'package:tutor/ui/module_tile.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/ui/plan_editor.dart';
import 'package:tutor/ui/plan_grid.dart';
import 'package:tutor/util/refresher.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/icon_field.dart';
import 'package:tutor/widgets/spoken_label.dart';

part 'plan_screen_fit.dart';

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
        !_runner.busy &&
        _editing(now) &&
        !samePlan(now?.plan, next?.plan),
  );
  late final StreamSubscription<int> _changes;
  final _comment = TextEditingController();
  bool _editorDirty = false;
  String? _editorKey;
  FoldResult? _fold;

  @override
  void initState() {
    super.initState();
    unawaited(_data.reload());
    unawaited(_refold());
    // Live while visible: the worker bumps rev.catalog as modules generate.
    _changes = widget.services.rev.catalogChanges.listen((_) {
      unawaited(_data.reload());
      unawaited(_refold());
    });
  }

  Future<void> _refold() async {
    final s = widget.services;
    final f = await foldAll(s.events, s.catalog);
    if (mounted) setState(() => _fold = f);
  }

  @override
  void dispose() {
    unawaited(_changes.cancel());
    unawaited(_runner.dispose());
    _data.dispose();
    _comment.dispose();
    super.dispose();
  }

  void _redraft(SubjectData data, Plan plan) {
    final c = _comment.text.trim();
    if (c.isEmpty) return;
    unawaited(_send(RequestBody.planRevise(data.id, plan.rev, c)));
  }

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
      title: const SpokenLabel(
        semanticLabel: 'Plan',
        child: Icon(Icons.assignment_outlined),
      ),
      actions: [
        GlyphButton(
          icon: Icons.refresh,
          semanticLabel: 'Reload',
          onPressed: _reload,
        ),
      ],
    ),
    body: ListenableBuilder(
      // The runner too: the comment box locks while a request runs.
      listenable: Listenable.merge([_data, _runner.changes]),
      builder: (context, _) {
        final error = _data.error;
        if (!_data.hasData) {
          return error == null
              ? const Center(child: CircularProgressIndicator())
              : _loadError(error);
        }
        final data = _data.data;
        if (data == null) return _missing();
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
    final progress = _fold == null
        ? null
        : subjectProgress(data, _fold!, DateTime.now());
    final header = _header(data);
    final list = PageList(
      children: [
        ...header,
        if (data.meta.status == SubjectStatus.failed ||
            plan == null ||
            data.meta.status == SubjectStatus.drafting)
          _pendingState(data)
        else if (_editing(data)) ...[
          if (plan.notes.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            ContentText(plan.notes, style: text.bodyMedium),
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
          const LearnHeader(Icons.rate_review_outlined, 'Ask for changes'),
          FieldLabel(
            semanticLabel: 'Comment (e.g. "less history, more maintenance")',
            child: TextField(
              controller: _comment,
              enabled: !_runner.busy,
              minLines: 2,
              maxLines: 5,
              decoration: iconDecoration(Icons.chat_bubble_outline),
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Align(
            alignment: Alignment.centerRight,
            child: GlyphButton(
              icon: Icons.auto_fix_high,
              semanticLabel: 'Redraft with this comment',
              onPressed: _runner.canSend ? () => _redraft(data, plan) : null,
            ),
          ),
        ] else ...[
          const LearnHeader(Icons.view_agenda_outlined, 'Modules'),
          for (final m in plan.modules)
            ModuleProgressTile(
              module: m,
              tally: progress?.modules[m.id],
              review: progress?.review[m.id],
              onRetry: () => _send(RequestBody.planApprove(data.id, plan.rev)),
              onReview: () => _review(data, m),
            ),
        ],
        if (plan != null && plan.history.isNotEmpty) ...[
          const LearnHeader(Icons.history, 'Revisions'),
          for (final h in plan.history) RevisionLine(h),
        ],
      ],
    );
    return _fit(data, list, header, progress);
  }
}
