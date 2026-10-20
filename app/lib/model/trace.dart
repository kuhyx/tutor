/// The model's thinking and research (DOCS-contract §6 `STEP`): a tutor
/// message's `trace` and the live `sessions/{sid}/progress` node. Display
/// only; read forgivingly (a malformed step is skipped, never an error).
library;

import 'package:tutor/model/json.dart';

/// One step: summarized thinking, or a tool call (what was searched,
/// fetched or run).
class TraceStep {
  /// Creates the step.
  const new({
    required this.kind,
    this.text = '',
    this.name = '',
    this.input = '',
  });

  /// `thinking` or `tool`.
  final String kind;

  /// Thinking text.
  final String text;

  /// Tool name (`WebSearch`, `WebFetch`, `Bash`, ...).
  final String name;

  /// What the tool was given: query, URL, command (one short line).
  final String input;

  /// A tool call.
  bool get isTool => kind == 'tool';

  /// Wire form.
  Json toJson() => isTool
      ? {'kind': 'tool', 'name': name, 'input': input}
      : {'kind': 'thinking', 'text': text};
}

TraceStep? _step(Object? raw) {
  if (raw is! Map<String, dynamic>) return null;
  String s(String k) => raw[k] is String ? raw[k] as String : '';
  return switch (raw['kind']) {
    'thinking' => TraceStep(kind: 'thinking', text: s('text')),
    'tool' => TraceStep(kind: 'tool', name: s('name'), input: s('input')),
    _ => null,
  };
}

/// [raw] (a list, or an RTDB node keyed `s0001`...) as steps in order;
/// adjacent thinking steps are joined (the worker streams them in pieces).
List<TraceStep> parseTrace(Object? raw) {
  final items = switch (raw) {
    final List<Object?> l => l,
    final Map<String, dynamic> m => [
      for (final k in m.keys.toList()..sort()) m[k],
    ],
    _ => const <Object?>[],
  };
  final out = <TraceStep>[];
  for (final step in items.map(_step).nonNulls) {
    if (!step.isTool && out.isNotEmpty && !out.last.isTool) {
      out.last = TraceStep(kind: 'thinking', text: out.last.text + step.text);
    } else {
      out.add(step);
    }
  }
  return out;
}

/// `sessions/{sid}/progress`: the trace of the request being served.
class LiveProgress {
  /// Creates the record.
  const new({required this.rid, this.steps = const []});

  /// The request it belongs to (shown only while `meta.busy.rid` matches).
  final String rid;

  /// Steps so far.
  final List<TraceStep> steps;

  /// Parses the node; null when absent or without a `rid`.
  static LiveProgress? parse(Object? node) {
    if (node is! Map<String, dynamic>) return null;
    final rid = node['rid'];
    if (rid is! String) return null;
    return LiveProgress(rid: rid, steps: parseTrace(node['steps']));
  }
}
