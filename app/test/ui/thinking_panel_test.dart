// The tutor's thinking: a collapsible panel under each tutor bubble
// (collapsed by default), and live while a turn is in flight, where the
// research steps show even while the reasoning is folded away.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/trace.dart';
import 'package:tutor/ui/session/message_tile.dart';
import 'package:tutor/ui/session/thinking_panel.dart';

const _thought = 'The learner knows coils; ask about the contact.';
final List<TraceStep> _steps = parseTrace([
  {'kind': 'thinking', 'text': _thought},
  {'kind': 'tool', 'name': 'WebSearch', 'input': 'relay contact NO NC'},
  {'kind': 'tool', 'name': 'WebFetch', 'input': 'https://example.org/relay'},
]);

Future<void> _pump(WidgetTester t, Widget child) => t.pumpWidget(
  MaterialApp(
    home: Scaffold(body: SingleChildScrollView(child: child)),
  ),
);

void main() {
  testWidgets('a tutor bubble with a trace: folded panel, opens on tap', (
    t,
  ) async {
    final m = Message.fromJson({
      'role': 'tutor',
      'text': 'What does the contact do?',
      'trace': [for (final s in _steps) s.toJson()],
    });
    await _pump(t, MessageTile(message: m));
    expect(find.text('Thinking · 2 research steps'), findsOneWidget);
    expect(find.text(_thought), findsNothing);
    expect(find.textContaining('relay contact NO NC'), findsNothing);
    await t.tap(find.text('Thinking · 2 research steps'));
    await t.pump();
    expect(find.text(_thought), findsOneWidget);
    expect(find.text('Search: relay contact NO NC'), findsOneWidget);
    expect(find.text('Fetch: https://example.org/relay'), findsOneWidget);
    await t.tap(find.text('Thinking · 2 research steps'));
    await t.pump();
    expect(find.text(_thought), findsNothing);
  });

  testWidgets('no trace: no panel', (t) async {
    final m = Message.fromJson({'role': 'tutor', 'text': 'Hi.'});
    await _pump(t, MessageTile(message: m));
    expect(find.byType(ThinkingPanel), findsNothing);
  });

  testWidgets('thinking only: the header says so', (t) async {
    await _pump(t, ThinkingPanel(steps: parseTrace([_steps.first.toJson()])));
    expect(find.text('Thinking'), findsOneWidget);
  });

  testWidgets('in flight: research shows live, reasoning folds, stays open', (
    t,
  ) async {
    await _pump(
      t,
      const LiveTrace(key: ValueKey('live-r1'), phase: Phase.thinking),
    );
    expect(find.text('Tutor is thinking...'), findsOneWidget);
    expect(find.byType(ThinkingPanel), findsNothing);

    await _pump(
      t,
      LiveTrace(
        key: const ValueKey('live-r1'),
        phase: Phase.thinking,
        steps: _steps.sublist(0, 2),
      ),
    );
    expect(find.text('Researching...'), findsOneWidget);
    // The research steps show while the reasoning is folded.
    expect(find.text('Search: relay contact NO NC'), findsOneWidget);
    expect(find.text(_thought), findsNothing);
    await t.tap(find.text('Thinking · 1 research step'));
    await t.pump();
    expect(find.text(_thought), findsOneWidget);

    // A later update (same request) keeps it open and adds the new step.
    await _pump(
      t,
      LiveTrace(
        key: const ValueKey('live-r1'),
        phase: Phase.thinking,
        steps: _steps,
      ),
    );
    expect(find.text(_thought), findsOneWidget);
    expect(find.text('Fetch: https://example.org/relay'), findsOneWidget);
    expect(find.text('Thinking · 2 research steps'), findsOneWidget);
  });

  testWidgets('other phases keep their own line', (t) async {
    await _pump(t, LiveTrace(phase: Phase.checkingImages, steps: _steps));
    expect(find.text('Checking the pictures...'), findsOneWidget);
  });

  testWidgets('any other tool shows with a generic icon', (t) async {
    final read = parseTrace([
      {'kind': 'tool', 'name': 'Read', 'input': '/notes/otto.md'},
    ]);
    await _pump(t, ThinkingPanel(steps: read, live: true));
    expect(find.text('Read: /notes/otto.md'), findsOneWidget);
    expect(find.byIcon(Icons.build_outlined), findsOneWidget);
  });

  test('tool lines name what was done', () {
    String line(String name, String input) => toolLine(
      parseTrace([
        {'kind': 'tool', 'name': name, 'input': input},
      ]).single,
    );
    expect(line('WebSearch', 'q'), 'Search: q');
    expect(line('WebFetch', 'u'), 'Fetch: u');
    expect(line('Bash', 'ls'), 'Run: ls');
    expect(line('Read', '/x'), 'Read: /x');
    expect(line('Grep', ''), 'Grep');
  });
}
