/// The lock's `/review/<subject>/<module>` route (`nav.openRoute`).
library;

import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/progress/card_progress.dart';
import 'package:tutor/review/review_items.dart';
import 'package:tutor/ui/nav.dart';

/// Opens the review of [module] of [subject] (the lock's `/review/...`): the
/// module's taught cards not yet passed ([moduleItems]). With none (nothing
/// taught, all passed, no cards) or a module the plan lacks, [subject]'s
/// plan instead. An unknown subject stays where it is, as [openLearn].
Future<void> openModuleReview(
  BuildContext context,
  TutorServices s,
  String subject,
  String module,
) async {
  final data = await s.catalog.fetch(subject);
  if (data == null || !context.mounted) return;
  final plan = data.plan?.modules.where((m) => m.id == module).firstOrNull;
  final ref = plan == null ? null : ModuleRef.of(subject, plan);
  final items = ref == null
      ? const <ReviewItem>[]
      : await moduleItems(catalog: s.catalog, events: s.events, module: ref);
  if (!context.mounted) return;
  if (ref == null || items.isEmpty) {
    await openPlan(context, s, subject);
  } else {
    await openReview(context, s, module: ref);
  }
}
