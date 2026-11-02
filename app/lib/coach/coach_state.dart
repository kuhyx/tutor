/// Session state in every coach result (DOCS-contract-coach.md "Open").
library;

import 'package:tutor/model/json.dart';

/// The gate before code: `req` (algorithm) or `shape` (SQL).
typedef Gate = ({String kind, int tries, int max, bool open, bool forced});

/// Phase `gate|work|exit|done`, turn budget, top rung, run status.
typedef CoachState = ({
  String phase,
  Gate gate,
  int used,
  int budget,
  bool over,
  String? rung,
  bool revealed,
  bool ranOk,
});

/// Before the worker has spoken: nothing is held back.
const CoachState openState = (
  phase: 'work',
  gate: (kind: 'req', tries: 0, max: 3, open: true, forced: false),
  used: 0,
  budget: 0,
  over: false,
  rung: null,
  revealed: false,
  ranOk: false,
);

/// Parses `state`; absent = null (the screen keeps its last one).
CoachState? parseState(Object? v) {
  if (v == null) return null;
  final j = asJson(v, 'state');
  final g = objOr(j, 'gate') ?? const <String, dynamic>{};
  final t = objOr(j, 'turns') ?? const <String, dynamic>{};
  return (
    phase: strOr(j, 'phase') ?? 'work',
    gate: (
      kind: strOr(g, 'kind') ?? 'req',
      tries: intOr(g, 'tries') ?? 0,
      max: intOr(g, 'max') ?? 3,
      open: g.isEmpty || flag(g, 'open'),
      forced: flag(g, 'forced'),
    ),
    used: intOr(t, 'used') ?? 0,
    budget: intOr(t, 'budget') ?? 0,
    over: flag(t, 'over'),
    rung: strOr(j, 'rung'),
    revealed: flag(j, 'revealed'),
    ranOk: flag(j, 'ran_ok'),
  );
}
