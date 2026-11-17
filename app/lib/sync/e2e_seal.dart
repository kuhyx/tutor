/// The tutor's sealed RTDB tree (DOCS-contract §12).
///
/// The rules live here; the sealing itself is the shared `rtdb_relay`
/// package (the Dart twin of `tutor/relay/e2e.py`). `contract/e2e_vectors.json`
/// pins both. Clear siblings are only the server timestamps (`req.created`,
/// `result.at`, presence `seen`/`beat`).
library;

import 'package:crdt_sync/crdt_sync.dart' show E2eLayout;
import 'package:rtdb_relay/rtdb_relay.dart';

export 'package:rtdb_relay/rtdb_relay.dart'
    show E2eLayoutError, E2eRule, E2eRuleKind, e2eParts, kSealedKey;

/// The pre-e2e root (`tutor/v1`): read once by the worker's copy, never
/// deleted.
const String kOldRoot = 'tutor/v1';

/// Where the tutor's data lives now: `tutor/v1-e2e`.
final E2eLayout kE2eLayout = E2eLayout.of(kOldRoot);

/// The tutor's tree rules.
final RelayLayout kTutorLayout = RelayLayout(
  kOldRoot,
  clear: const [
    'meta',
    'rev',
    'migration',
    'requests/*/claim',
    'sessions/*/progress/rid',
  ],
  units: const {
    'live': {},
    'prefs/*': {},
    'stats/*': {},
    'presence/workers/*': {'beat'},
    'presence/clients/*': {'seen'},
    'uploads/*/*': {},
    'requests/*/req': {'created'},
    'requests/*/result': {'at'},
    'sessions/*/meta/*': {},
    'sessions/*/msgs/*': {},
    'sessions/*/receipts/*': {},
    'sessions/*/user/*': {},
    'sessions/*/progress/steps/*': {},
    'session_index/*': {},
    'subjects/*/meta': {},
    'subjects/*/plan': {},
    'subjects/*/cards': {},
    'subjects/*/concepts': {},
    'log/*/*': {},
    'feedback/*': {},
  },
);

/// The rule for the node at [parts] (relative to the e2e root).
E2eRule classifyE2e(List<String> parts) => kTutorLayout.classify(parts);

/// Seals writes and opens reads of the tutor's tree.
class TutorSealer extends RelaySealer {
  /// Creates the sealer; [root] overrides `tutor/v1-e2e`.
  new(super.cipher, {super.root}) : super(layout: kTutorLayout);
}
