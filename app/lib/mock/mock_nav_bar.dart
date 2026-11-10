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

  /// The task's section glyph and its number within the section (the code
  /// section has one task: no number).
  Widget _label(int i) {
    final t = s.paper.tasks[i];
    final n = s.paper.tasks
        .take(i + 1)
        .where((o) => o.section == t.section)
        .length;
    final (icon, spoken) = switch (t.section) {
      MockSection.pyMcq => (Icons.quiz_outlined, 'Multiple choice'),
      MockSection.pyCode => (Icons.code, 'Python code'),
      MockSection.sql => (Icons.storage_outlined, 'SQL'),
    };
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, semanticLabel: spoken),
        if (t.section != MockSection.pyCode) ...[
          const SizedBox(width: AppSpacing.xs),
          Text('$n'),
        ],
      ],
    );
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
              label: _label(i),
              onSelected: (_) => s.update(go: i),
            ),
          ),
      ],
    ),
  );
}
