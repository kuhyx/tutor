/// The fixture's one live change, so screenshots can show a screen updating
/// by itself: car's "Clutch, gearbox, drivetrain" starts `generating`, and
/// a while after the app opens the worker "finishes" it (`ready`, three
/// cards) and bumps `rev.catalog`, as the real worker does.
library;

import 'package:tutor/sync/json_tree.dart';

const _plan = 'tutor/v1/subjects/car/plan/modules';
const _cards = 'tutor/v1/subjects/car/cards';
const _drivetrain = 2;

/// Seconds from the first `rev` listen to the change; `?bump=<s>` sets it.
Duration fixtureBumpDelay(Map<String, String> query) =>
    Duration(seconds: int.tryParse(query['bump'] ?? '') ?? 20);

Object? _patchModule(Object? root, Map<String, Object> patch) {
  final modules = [...getAt(root, _plan)! as List<Object?>];
  modules[_drivetrain] = {
    ...modules[_drivetrain]! as Map<String, dynamic>,
    ...patch,
  };
  return setAt(root, _plan, modules);
}

/// [root] with the drivetrain module generating (the starting state).
Object? fixtureGenerating(Object? root) =>
    _patchModule(root, {'status': 'generating', 'cards': 0});

/// [root] with the drivetrain module ready, its cards written, and
/// `rev.catalog` bumped.
Object? fixtureCardsReady(Object? root) {
  var next = _patchModule(root, {'status': 'ready', 'cards': 3});
  final template = getAt(next, '$_cards/eng-strokes')! as Map<String, dynamic>;
  const fronts = {
    'drv-clutch': 'What does the clutch do?',
    'drv-gears': 'Why does a car need gears?',
    'drv-diff': 'What does the differential allow?',
  };
  var order = 1;
  for (final MapEntry(:key, :value) in fronts.entries) {
    next = setAt(next, '$_cards/$key', {
      ...template,
      'module': 'drivetrain',
      'order': order++,
      'front': value,
    });
  }
  final rev = getAt(next, 'tutor/v1/rev/catalog')! as int;
  return setAt(next, 'tutor/v1/rev/catalog', rev + 1);
}
