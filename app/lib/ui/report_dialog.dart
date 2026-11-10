/// Report a problem (`static/report.js`): for the developer, never sent to
/// the tutor. Optionally about one message. The text is kept when saving
/// fails.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/feedback/feedback_sender.dart';
import 'package:tutor/model/stats.dart' as stats;
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/count_badge.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/icon_field.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// The report form.
class ReportDialog extends StatefulWidget {
  /// Creates the form.
  const new({
    required this.sender,
    required this.route,
    this.session,
    this.msg,
    this.preview,
    super.key,
  });

  /// Writes the report.
  final FeedbackSender sender;

  /// Screen it was opened from.
  final String route;

  /// Session it is about.
  final String? session;

  /// Message it is about.
  final String? msg;

  /// That message's text, for the scope line.
  final String? preview;

  @override
  State<ReportDialog> createState() => _ReportDialogState();
}

class _ReportDialogState extends State<ReportDialog> {
  late stats.FeedbackCategory _category = widget.msg == null
      ? stats.FeedbackCategory.experience
      : stats.FeedbackCategory.response;
  final _text = TextEditingController();
  String? _error;
  String? _saved;
  bool _busy = false;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final fid = await widget.sender.send(
        category: _category,
        text: _text.text,
        route: widget.route,
        session: widget.session,
        msg: widget.msg,
      );
      setState(() => _saved = fid);
    } on Object catch (error) {
      // `on Object`: an empty text is an ArgumentError; both are shown and
      // the report stays in the box.
      setState(() => _error = 'Not saved: $error. Your report is kept.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.preview?.replaceAll(RegExp(r'\s+'), ' ') ?? '';
    if (_saved != null) {
      return AlertDialog(
        content: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CueChip(kind: CueKind.ok, semanticLabel: 'Report saved'),
            const SizedBox(width: AppSpacing.md),
            IdChip(_saved!),
          ],
        ),
        actions: [
          GlyphButton(
            icon: Icons.check,
            semanticLabel: 'Close',
            filled: true,
            onPressed: () => Navigator.pop(context),
          ),
        ],
      );
    }
    return AlertDialog(
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // About one tutor message: its text (content), shortened.
            if (widget.msg != null)
              Row(
                children: [
                  const Icon(
                    Icons.chat_bubble_outline,
                    semanticLabel: 'About a tutor message',
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: ContentText(
                      p.length > 90 ? '${p.substring(0, 90)}...' : p,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                ],
              ),
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.sm,
              children: [
                for (final (c, icon, label) in _categories)
                  ChoiceChip(
                    key: ValueKey('report-${c.name}'),
                    label: Icon(icon, semanticLabel: label),
                    selected: _category == c,
                    onSelected: (_) => setState(() => _category = c),
                  ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            FieldLabel(
              semanticLabel: 'What is wrong?',
              child: TextField(
                controller: _text,
                autofocus: true,
                maxLength: stats.Feedback.maxText,
                maxLines: 5,
                minLines: 3,
                decoration: iconDecoration(Icons.edit_note),
              ),
            ),
            if (_error != null)
              CueChip(
                key: ValueKey(_error),
                kind: CueKind.error,
                semanticLabel: _error!,
              ),
          ],
        ),
      ),
      actions: [
        GlyphButton(
          icon: Icons.close,
          semanticLabel: 'Cancel',
          onPressed: () => Navigator.pop(context),
        ),
        GlyphButton(
          icon: Icons.save_outlined,
          semanticLabel: 'Save report',
          filled: true,
          onPressed: _busy ? null : _submit,
        ),
      ],
    );
  }
}

/// The report categories as glyph chips: UI, response, experience, other.
const List<(stats.FeedbackCategory, IconData, String)> _categories = [
  (stats.FeedbackCategory.ui, Icons.dashboard_outlined, 'UI'),
  (
    stats.FeedbackCategory.response,
    Icons.smart_toy_outlined,
    "Tutor's response",
  ),
  (
    stats.FeedbackCategory.experience,
    Icons.sentiment_neutral,
    'Overall experience',
  ),
  (stats.FeedbackCategory.other, Icons.more_horiz, 'Other'),
];
