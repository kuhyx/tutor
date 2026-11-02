import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/mock/mock_models.dart';
import 'package:tutor/mock/mock_session.dart';

/// Chips to jump between tasks; a check marks a submitted one.
class MockNavBar extends StatelessWidget {
  /// Creates the bar.
  const new(this.s, {super.key});

  /// The test.
  final MockSession s;

  String _label(int i) {
    final t = s.paper.tasks[i];
    final n = s.paper.tasks
        .take(i + 1)
        .where((o) => o.section == t.section)
        .length;
    return switch (t.section) {
      MockSection.pyMcq => 'M$n',
      MockSection.pyCode => 'PY',
      MockSection.sql => 'S$n',
    };
  }

  @override
  Widget build(BuildContext context) => SizedBox(
    height: 52,
    child: ListView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
      children: [
        for (final (i, t) in s.paper.tasks.indexed)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs),
            child: ChoiceChip(
              key: ValueKey('nav-$i'),
              selected: i == s.index,
              avatar: s.isSubmitted(t.id)
                  ? const Icon(Icons.check_circle, size: 16)
                  : null,
              label: Text(_label(i)),
              onSelected: (_) => s.update(go: i),
            ),
          ),
      ],
    ),
  );
}
