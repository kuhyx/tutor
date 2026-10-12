/// Report a problem (`static/report.js`): for the developer, never sent to
/// the tutor. Optionally about one message. The text is kept when saving
/// fails.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/feedback/feedback_sender.dart';
import 'package:tutor/model/stats.dart' as stats;

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
    final scope = widget.msg == null
        ? 'About the UI or the experience as a whole.'
        : 'About tutor message ${widget.msg}: '
              '"${p.length > 90 ? '${p.substring(0, 90)}...' : p}"';
    if (_saved != null) {
      return AlertDialog(
        title: const Text('Report saved'),
        content: Text('Saved as feedback $_saved.'),
        actions: [
          FilledButton(
            autofocus: true,
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      );
    }
    return AlertDialog(
      title: const Text('Report a problem'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('For the developer, not sent to the tutor.'),
            const SizedBox(height: AppSpacing.sm),
            Text(scope, style: Theme.of(context).textTheme.bodySmall),
            DropdownButton<stats.FeedbackCategory>(
              value: _category,
              isExpanded: true,
              items: const [
                DropdownMenuItem(
                  value: stats.FeedbackCategory.ui,
                  child: Text('UI'),
                ),
                DropdownMenuItem(
                  value: stats.FeedbackCategory.response,
                  child: Text("Tutor's response"),
                ),
                DropdownMenuItem(
                  value: stats.FeedbackCategory.experience,
                  child: Text('Overall experience'),
                ),
                DropdownMenuItem(
                  value: stats.FeedbackCategory.other,
                  child: Text('Other'),
                ),
              ],
              onChanged: (v) => setState(() => _category = v ?? _category),
            ),
            TextField(
              controller: _text,
              autofocus: true,
              maxLength: stats.Feedback.maxText,
              maxLines: 5,
              minLines: 3,
              decoration: const InputDecoration(
                labelText: 'What is wrong?',
                hintText: 'e.g. it posted the same image twice',
              ),
            ),
            if (_error != null)
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _busy ? null : _submit,
          child: const Text('Save report'),
        ),
      ],
    );
  }
}
