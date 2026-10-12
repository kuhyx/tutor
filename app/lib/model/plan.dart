/// `subjects/{subj}/plan` (curriculum §2, worker-written).
library;

import 'package:tutor/model/json.dart';

/// Module status.
enum ModuleStatus {
  /// Requirements not mastered yet.
  locked,

  /// Cards being generated.
  generating,

  /// Cards available.
  ready,

  /// Recall >= 0.8.
  mastered,

  /// Generation failed (see `error`).
  failed;

  /// Parses a wire name.
  static ModuleStatus parse(String s) => byWire(values, s, (v) => v.name);
}

/// One plan module.
class Module {
  /// Creates the record.
  const new({
    required this.id,
    required this.title,
    this.summary = '',
    this.requires = const [],
    this.depth = 1,
    this.prefixes = const [],
    this.status = ModuleStatus.locked,
    this.recall = 0,
    this.cards = 0,
    this.error,
  });

  /// Parses a module.
  factory fromJson(Object? v) {
    final j = asJson(v, 'module');
    return Module(
      id: str(j, 'id'),
      title: str(j, 'title'),
      summary: strOr(j, 'summary') ?? '',
      requires: strings(j, 'requires'),
      depth: intOr(j, 'depth') ?? 1,
      prefixes: strings(j, 'prefixes'),
      status: ModuleStatus.parse(strOr(j, 'status') ?? 'locked'),
      recall: dblOr(j, 'recall') ?? 0,
      cards: intOr(j, 'cards') ?? 0,
      error: strOr(j, 'error'),
    );
  }

  /// Module id (slug).
  final String id;

  /// Title.
  final String title;

  /// Summary (<= 300 chars).
  final String summary;

  /// Earlier module ids that must be mastered first.
  final List<String> requires;

  /// Go-deeper round (1 = first plan).
  final int depth;

  /// Card id prefixes (automation id rule).
  final List<String> prefixes;

  /// Status.
  final ModuleStatus status;

  /// Share of good cards.
  final double recall;

  /// Card count.
  final int cards;

  /// Why generation failed.
  final String? error;

  /// Wire form (empty lists omitted: RTDB stores none).
  Json toJson() => compact({
    'id': id,
    'title': title,
    'summary': summary,
    'requires': requires.isEmpty ? null : requires,
    'depth': depth,
    'prefixes': prefixes.isEmpty ? null : prefixes,
    'status': status.name,
    'recall': recall,
    'cards': cards,
    'error': error,
  });
}

/// A plan revision note.
class PlanChange {
  /// Creates the record.
  const new({required this.rev, required this.comment, required this.at});

  /// Parses an entry.
  factory fromJson(Object? v) {
    final j = asJson(v, 'history');
    return PlanChange(
      rev: integer(j, 'rev'),
      comment: str(j, 'comment'),
      at: integer(j, 'at'),
    );
  }

  /// Revision the comment applied to.
  final int rev;

  /// kuhy's comment.
  final String comment;

  /// When.
  final int at;

  /// Wire form.
  Json toJson() => {'rev': rev, 'comment': comment, 'at': at};
}

/// `subjects/{subj}/plan`.
class Plan {
  /// Creates the record.
  const new({
    required this.rev,
    required this.status,
    this.notes = '',
    this.modules = const [],
    this.history = const [],
  });

  /// Parses `plan`.
  factory fromJson(Json j) => Plan(
    rev: integer(j, 'rev'),
    status: str(j, 'status'),
    notes: strOr(j, 'notes') ?? '',
    modules: listOf(j, 'modules', Module.fromJson),
    history: listOf(j, 'history', PlanChange.fromJson),
  );

  /// Plan revision (every plan op carries it; mismatch = `plan_conflict`).
  final int rev;

  /// `draft` or `approved`.
  final String status;

  /// Why this order.
  final String notes;

  /// Modules in teaching order.
  final List<Module> modules;

  /// Revision comments.
  final List<PlanChange> history;

  /// Wire form.
  Json toJson() => compact({
    'rev': rev,
    'status': status,
    'notes': notes.isEmpty ? null : notes,
    'modules': modules.isEmpty ? null : [for (final m in modules) m.toJson()],
    'history': history.isEmpty ? null : [for (final h in history) h.toJson()],
  });
}
