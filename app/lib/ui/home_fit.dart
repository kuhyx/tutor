/// Home on a phone: the Today card, then a paged grid of subject tiles and
/// a "+" tile; a tile's sheet holds the full subject card and its actions.
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/home/home_loader.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/progress/progress.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/fit_parts.dart';
import 'package:tutor/ui/home_body.dart';
import 'package:tutor/ui/new_subject_field.dart';
import 'package:tutor/ui/subject_tile.dart';
import 'package:tutor/widgets/spoken_label.dart';
import 'package:tutor/widgets/status_glyph.dart';

/// The phone body of Home.
class HomeFit extends StatelessWidget {
  /// Creates the body.
  const new({required this.body, required this.today, super.key});

  /// Data and callbacks.
  final HomeBody body;

  /// Offline notices and the Today card, as on the desktop.
  final List<Widget> today;

  @override
  Widget build(BuildContext context) {
    final subjects = body.data.subjects;
    return fitPage([
      _pad(Column(mainAxisSize: MainAxisSize.min, children: today)),
      _pad(RequestStatusLine(body.runner)),
      const SizedBox(height: AppSpacing.sm),
      Expanded(
        child: FitTileGrid(
          itemCount: subjects.length + 1,
          itemBuilder: (context, i) => i < subjects.length
              ? _subject(context, subjects[i])
              : _NewTile(body),
        ),
      ),
    ]);
  }

  Widget _subject(BuildContext context, SubjectEntry s) {
    final data = body.data;
    final status = s.meta.status;
    final current = s.id == data.currentSubject;
    final teaching =
        status == SubjectStatus.active || status == SubjectStatus.completed;
    final (reviewed, total) = s.data == null ? (0, 0) : masteredOf(s.data!);
    final due = data.dueBySubject[s.id] ?? 0;
    return FitTile(
      key: ValueKey('subject-tile-${s.id}'),
      title: s.meta.title,
      lines: [if (total > 0) '$reviewed/$total'],
      meta: [StatusGlyph(status, detail: s.meta.error, size: 16)],
      corner: [
        if (current)
          const Icon(
            Icons.radio_button_checked,
            size: 16,
            semanticLabel: 'New material from here',
          ),
        if (due > 0) Badge(label: Text('$due')),
      ],
      marked: data.toReview[s.id] != null || status == SubjectStatus.failed,
      onTap: teaching && !current
          ? () => body.onPick(s.id)
          : () => body.onPlan(s.id),
      onMore: () => _sheet(context, s, current: current, due: due),
    );
  }

  void _sheet(
    BuildContext context,
    SubjectEntry s, {
    required bool current,
    required int due,
  }) {
    final data = body.data;
    final reviewDue = body.onReviewSubject;
    final reviewModule = body.onReviewModule;
    unawaited(
      showFitSheet(
        context,
        title: s.meta.title,
        children: (sheet) {
          VoidCallback close(VoidCallback run) => () {
            Navigator.of(sheet).pop();
            run();
          };
          return [
            SubjectTile(
              entry: s,
              toReview: data.toReview[s.id],
              tally: data.cardTally[s.id],
              due: due,
              current: current,
              onReviewModule: reviewModule == null
                  ? null
                  : (m) => close(() => reviewModule(m))(),
              onReviewDue: reviewDue == null
                  ? null
                  : close(() => reviewDue(s.id, s.meta.title)),
              onPlan: close(() => body.onPlan(s.id)),
              onEdit: close(() => body.onEdit(s.id)),
              onPick: close(() => body.onPick(s.id)),
              onFinish: (deeper) =>
                  close(() => body.onFinish(s.id, goDeeper: deeper))(),
              onRetry: close(() => body.onNewSubject(s.meta.goal)),
            ),
          ];
        },
      ),
    );
  }
}

class _NewTile extends StatelessWidget {
  const new(this.body);

  final HomeBody body;

  @override
  Widget build(BuildContext context) {
    void open() => unawaited(
      showDialog<void>(context: context, builder: (_) => _NewDialog(body)),
    );
    return SpokenLabel(
      semanticLabel: 'New subject',
      button: true,
      onTap: open,
      child: Card(
        margin: EdgeInsets.zero,
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: open,
          child: const Center(child: Icon(Icons.add, size: 40)),
        ),
      ),
    );
  }
}

class _NewDialog extends StatefulWidget {
  const new(this.body);

  final HomeBody body;

  @override
  State<_NewDialog> createState() => _NewDialogState();
}

class _NewDialogState extends State<_NewDialog> {
  // The runner is shared: only this dialog's own request closes it.
  bool _sent = false;

  @override
  void initState() {
    super.initState();
    widget.body.runner.status.addListener(_onStatus);
  }

  @override
  void dispose() {
    widget.body.runner.status.removeListener(_onStatus);
    super.dispose();
  }

  // Done: close before Home opens the new plan, so Back lands on Home.
  void _onStatus() {
    if (_sent && widget.body.runner.status.value is RelayDone && mounted) {
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    content: SizedBox(
      width: 400,
      child: NewSubjectField(
        runner: widget.body.runner,
        onSubmit: (text) {
          _sent = true;
          widget.body.onNewSubject(text);
        },
      ),
    ),
  );
}

Widget _pad(Widget child) => Padding(
  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
  child: child,
);
