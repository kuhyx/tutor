part of 'plan_screen.dart';

const Set<SubjectStatus> _pending = {
  SubjectStatus.failed,
  SubjectStatus.drafting,
};

extension on _PlanScreenState {
  Widget _loadError(Object error) => PageList(
    children: [
      CueChip(kind: CueKind.error, semanticLabel: 'Could not load: $error'),
    ],
  );

  Widget _missing() => const PageList(
    children: [
      SizedBox(
        height: 240,
        child: GlyphEmpty(
          icon: Icons.help_outline,
          semanticLabel: 'This subject does not exist (yet).',
        ),
      ),
    ],
  );

  // Drafting failed, or the tutor is still drafting.
  Widget _pendingState(SubjectData data) => SizedBox(
    height: 240,
    child: data.meta.status == SubjectStatus.failed
        ? GlyphEmpty(
            icon: Icons.error_outline,
            tint: Theme.of(context).colorScheme.error,
            semanticLabel:
                'Drafting the plan failed. '
                '${data.meta.error ?? 'Try again from Home.'}',
          )
        : const GlyphEmpty(
            icon: Icons.hourglass_empty,
            semanticLabel:
                'The tutor is drafting the plan. It appears here by itself '
                'when the PC is done.',
          ),
  );

  // Reload banner, refresh error, the subject's name (content), its goal,
  // a status glyph and the request's status.
  List<Widget> _header(SubjectData data) {
    final text = Theme.of(context).textTheme;
    return [
      if (_data.hasPending)
        MaterialBanner(
          content: const CueChip(
            kind: CueKind.blocked,
            icon: Icons.sync_problem,
            semanticLabel: 'Plan changed — reload',
          ),
          actions: [
            GlyphButton(
              icon: Icons.refresh,
              semanticLabel: 'Reload plan',
              onPressed: _data.applyPending,
            ),
          ],
        ),
      if (_data.error != null)
        CueChip(
          kind: CueKind.error,
          semanticLabel: 'Could not refresh: ${_data.error}',
        ),
      ContentText(data.meta.title, style: text.headlineSmall),
      if (data.meta.goal.isNotEmpty) ContentText(data.meta.goal),
      const SizedBox(height: AppSpacing.sm),
      SubjectStatusIcon(data.meta.status),
      RequestStatusLine(_runner),
    ];
  }

  Widget _fit(
    SubjectData data,
    Widget list,
    List<Widget> header,
    SubjectProgress? progress,
  ) {
    final plan = data.plan;
    if (plan == null || _PlanScreenState._editing(data)) return list;
    if (_pending.contains(data.meta.status)) return list;
    return planLayout(
      list,
      () => PlanFit(
        header: header,
        plan: plan,
        progress: progress,
        onRetry: () => _send(RequestBody.planApprove(data.id, plan.rev)),
        onReview: (m) => _review(data, m),
      ),
    );
  }

  // The tile shows the result.
  Future<void> _review(SubjectData data, Module m) => openReview(
    context,
    widget.services,
    module: ModuleRef.of(data.id, m),
  ).then((_) => _refold());
}
