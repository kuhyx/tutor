/// Review's end of run: nothing due / nothing to review, or All done.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/review/review_session.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/review_answer.dart';

/// The screen once [run] has no card left (or never had one).
class ReviewEnd extends StatelessWidget {
  /// Creates the end state; [module] = a module review, not the due queue.
  const new(this.run, {required this.module, super.key});

  /// The finished run.
  final ReviewSession run;

  /// A module review.
  final bool module;

  @override
  Widget build(BuildContext context) {
    final n = run.cardsDone;
    final empty = run.items.isEmpty;
    return PageList(
      children: [
        EmptyState(
          icon: Icons.check_circle_outline,
          title: empty
              ? (module ? 'Nothing to review' : 'Nothing due')
              : 'All done',
          message: empty
              ? (module
                    ? 'No card of this module is taught yet.'
                    : 'Cards come back here when they are due.')
              : 'Reviewed $n card${n == 1 ? '' : 's'}. '
                    'Reviews sync when online.',
        ),
        // A mistaken rating on the last card is fixed from here.
        Center(child: ReviewBack(run)),
      ],
    );
  }
}
