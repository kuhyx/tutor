/// A subject's lifecycle status as a glyph (shape + tint); the status word
/// is spoken only.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/codes.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/ui/code_glyphs.dart';

/// The glyph of [status].
IconData statusIcon(SubjectStatus status) => switch (status) {
  SubjectStatus.drafting => Icons.autorenew,
  SubjectStatus.draft => Icons.edit_note,
  SubjectStatus.active => Icons.play_circle_outline,
  SubjectStatus.completed => Icons.verified_outlined,
  SubjectStatus.reviewOnly => Icons.history,
  SubjectStatus.failed => Icons.error_outline,
};

/// The tint of [status]; null = the surrounding colour.
Color? statusTint(BuildContext context, SubjectStatus status) =>
    switch (status) {
      SubjectStatus.active => AppPalette.success,
      SubjectStatus.completed => AppPalette.success,
      SubjectStatus.drafting => AppPalette.warning,
      SubjectStatus.failed => Theme.of(context).colorScheme.error,
      SubjectStatus.draft || SubjectStatus.reviewOnly => null,
    };

/// The status glyph; [detail] (a failure's reason) is added to the spoken
/// label.
class StatusGlyph extends StatelessWidget {
  /// Creates the glyph.
  const new(
    this.status, {
    this.detail,
    this.errorKind = ErrorKind.other,
    this.size,
    super.key,
  });

  /// The status.
  final SubjectStatus status;

  /// Extra spoken detail (the worker's error), never painted.
  final String? detail;

  /// Why a `failed` status failed: its glyph replaces the generic one
  /// (other = the generic error glyph).
  final ErrorKind errorKind;

  /// Glyph size; null = the theme's.
  final double? size;

  @override
  Widget build(BuildContext context) => Icon(
    status == SubjectStatus.failed && errorKind != ErrorKind.other
        ? errorKindIcon(errorKind)
        : statusIcon(status),
    color: statusTint(context, status),
    size: size,
    semanticLabel: [
      status.wire.replaceAll('_', ' '),
      if (detail != null && detail!.isNotEmpty) detail!,
    ].join(' · '),
  );
}
