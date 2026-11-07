part of 'plan_screen.dart';

const Set<SubjectStatus> _pending = {
  SubjectStatus.failed,
  SubjectStatus.drafting,
};

extension on _PlanScreenState {
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
