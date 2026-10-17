/// Editing a draft plan on the client before `plan_edit` (curriculum §2):
/// rename, reorder, add, remove a module without cards, edit `requires`.
///
/// Every op returns a new list; [planProblems] says whether the result may
/// be sent (array order = teaching order, so `requires` must name EARLIER
/// modules). The worker validates again; this keeps kuhy from sending a
/// plan that can only come back `bad_request`.
library;

import 'dart:convert';

import 'package:tutor/model/ids.dart';
import 'package:tutor/model/plan.dart';

/// Module count a draft must stay within (curriculum §2).
const kMinModules = 3;

/// Upper bound on modules per draft.
const kMaxModules = 12;

Module _with(
  Module m, {
  String? title,
  String? summary,
  List<String>? requires,
}) => Module(
  id: m.id,
  title: title ?? m.title,
  summary: summary ?? m.summary,
  requires: requires ?? m.requires,
  depth: m.depth,
  prefixes: m.prefixes,
  status: m.status,
  recall: m.recall,
  cards: m.cards,
  error: m.error,
);

/// Renames module [i] (and optionally replaces its summary).
List<Module> renameModule(
  List<Module> modules,
  int i,
  String title, {
  String? summary,
}) => [
  for (final (n, m) in modules.indexed)
    if (n == i) _with(m, title: title.trim(), summary: summary?.trim()) else m,
];

/// Moves module [from] to index [to] (clamped).
List<Module> moveModule(List<Module> modules, int from, int to) {
  final out = [...modules];
  final m = out.removeAt(from);
  out.insert(to.clamp(0, out.length), m);
  return out;
}

/// Whether module [m] may be removed: only while it has no cards and is
/// still `locked` (curriculum §2: the worker restores any other module
/// verbatim).
bool editable(Module m) => m.cards == 0 && m.status == ModuleStatus.locked;

/// Removes module [i] (only [editable] ones) and drops it from every
/// `requires`.
List<Module> removeModule(List<Module> modules, int i) {
  final gone = modules[i];
  if (!editable(gone)) {
    throw StateError('module ${gone.id} has cards and cannot be removed');
  }
  return [
    for (final (n, m) in modules.indexed)
      if (n != i)
        if (m.requires.contains(gone.id))
          _with(m, requires: [...m.requires]..remove(gone.id))
        else
          m,
  ];
}

/// Base letter + combining mark -> the precomposed Polish letter, so an NFD
/// spelling slugs like the NFC one (Dart has no normalizer; `ł` has no
/// decomposition). Python does `unicodedata.normalize('NFC', ...)`.
final _composePolish = RegExp('[acenosz][̨́̇]');
const _composed = {
  'ą': 'ą',
  'ć': 'ć',
  'ę': 'ę',
  'ń': 'ń',
  'ó': 'ó',
  'ś': 'ś',
  'ź': 'ź',
  'ż': 'ż',
};

/// Slug of [title], unique among [taken] (`-2`, `-3`... appended). Keeps the
/// Polish letters (see [slugChars]); same rules as the worker's `slug()`.
String slugFor(String title, Iterable<String> taken) {
  final words = title
      .toLowerCase()
      .replaceAllMapped(_composePolish, (m) => _composed[m[0]] ?? m[0]!)
      .replaceAll(RegExp('[^$slugChars]+'), ' ')
      .trim()
      .split(' ')
      .where((w) => w.isNotEmpty);
  var base = words.join('-');
  if (base.isEmpty) base = 'module';
  if (base.length > 40) {
    base = base.substring(0, 40).replaceAll(RegExp(r'-$'), '');
  }
  final used = taken.toSet();
  var id = base;
  for (var n = 2; used.contains(id); n++) {
    id = '$base-$n';
  }
  return id;
}

/// Appends a new module titled [title], depth of the last module.
List<Module> addModule(List<Module> modules, String title) => [
  ...modules,
  Module(
    id: slugFor(title, modules.map((m) => m.id)),
    title: title.trim(),
    depth: modules.isEmpty ? 1 : modules.last.depth,
  ),
];

/// Sets module [i]'s `requires`.
List<Module> setRequires(List<Module> modules, int i, List<String> requires) =>
    [
      for (final (n, m) in modules.indexed)
        if (n == i) _with(m, requires: requires) else m,
    ];

/// Why [modules] cannot be sent; empty when it can.
List<String> planProblems(List<Module> modules) {
  final problems = <String>[];
  // A go-deeper draft appends: only the newest depth is counted.
  final depth = modules.fold(1, (d, m) => m.depth > d ? m.depth : d);
  final count = modules.where((m) => m.depth == depth).length;
  if (count < kMinModules || count > kMaxModules) {
    problems.add(
      'A plan has $kMinModules-$kMaxModules new modules '
      '(this one has $count).',
    );
  }
  final earlier = <String>{};
  for (final m in modules) {
    if (m.title.trim().isEmpty) problems.add('Module ${m.id} has no title.');
    if (!isSlug(m.id)) problems.add('Module id "${m.id}" is not valid.');
    if (earlier.contains(m.id)) problems.add('Module ${m.id} appears twice.');
    for (final r in m.requires) {
      if (!earlier.contains(r)) {
        problems.add('"${m.title}" requires "$r", which is not before it.');
      }
    }
    earlier.add(m.id);
  }
  return problems;
}

/// Whether [a] and [b] are the same plan on the wire (a refetch that only
/// moved another subject must not count as "the plan changed").
bool samePlan(Plan? a, Plan? b) =>
    jsonEncode(a?.toJson()) == jsonEncode(b?.toJson());
