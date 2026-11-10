/// The questions an interview milestone asks, behind one seam so widget
/// tests answer them without driving Material pickers. No words: icons only
/// (textgate); the pickers are the app's digit-only ones.
library;

import 'package:flutter/material.dart';
import 'package:tutor/ui/interview_labels.dart';
import 'package:tutor/ui/interview_time_dialog.dart';
import 'package:tutor/ui/numeric_date_picker.dart';

/// Answers to the interview prompts; null = dismissed.
abstract interface class InterviewPrompts {
  /// Trip this weekend: true yes, false no.
  Future<bool?> askTrip(BuildContext context);

  /// An inclusive day range within [first]..[last].
  Future<({DateTime start, DateTime end})?> pickRange(
    BuildContext context, {
    required DateTime first,
    required DateTime last,
  });

  /// A day and a time within [first]..[last].
  Future<DateTime?> pickDateTime(
    BuildContext context, {
    required DateTime first,
    required DateTime last,
  });

  /// A number >= 0.
  Future<double?> askScore(BuildContext context);

  /// A confirm tap: true confirms, false asks to redo, null dismisses.
  Future<bool?> confirm(BuildContext context);
}

typedef _Option = ({String key, IconData icon, bool value});

/// The Material implementation.
class MaterialPrompts implements InterviewPrompts {
  /// Creates it.
  const new();

  @override
  Future<bool?> askTrip(BuildContext context) => _choice(context, [
    (key: 'interview-trip-yes', icon: Icons.luggage, value: true),
    (key: 'interview-trip-no', icon: Icons.close, value: false),
  ]);

  @override
  Future<bool?> confirm(BuildContext context) => _choice(context, [
    (key: 'interview-confirm', icon: Icons.check, value: true),
    (key: 'interview-redo', icon: Icons.edit_calendar, value: false),
  ]);

  @override
  Future<({DateTime start, DateTime end})?> pickRange(
    BuildContext context, {
    required DateTime first,
    required DateTime last,
  }) async {
    final start = await showNumericDatePicker(
      context: context,
      initialDate: first,
      firstDate: first,
      lastDate: last,
    );
    if (start == null || !context.mounted) return null;
    final end = await showNumericDatePicker(
      context: context,
      initialDate: start,
      firstDate: start,
      lastDate: last,
    );
    return end == null ? null : (start: start, end: end);
  }

  @override
  Future<DateTime?> pickDateTime(
    BuildContext context, {
    required DateTime first,
    required DateTime last,
  }) async {
    final day = await showNumericDatePicker(
      context: context,
      initialDate: first,
      firstDate: first,
      lastDate: last,
    );
    if (day == null || !context.mounted) return null;
    final time = await showDigitTimePicker(
      context: context,
      initialTime: const TimeOfDay(hour: 9, minute: 0),
    );
    if (time == null) return null;
    return DateTime(day.year, day.month, day.day, time.hour, time.minute);
  }

  @override
  Future<double?> askScore(BuildContext context) => showDialog<double>(
    context: context,
    builder: (_) => const _ScoreDialog(),
  );

  Future<bool?> _choice(BuildContext context, List<_Option> options) =>
      showDialog<bool>(
        context: context,
        builder: (ctx) => SimpleDialog(
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                for (final o in options)
                  IconButton.filledTonal(
                    key: ValueKey(o.key),
                    iconSize: 32,
                    onPressed: () => Navigator.of(ctx).pop(o.value),
                    icon: Semantics(label: a11y(o.key), child: Icon(o.icon)),
                  ),
              ],
            ),
          ],
        ),
      );
}

class _ScoreDialog extends StatefulWidget {
  const new();

  @override
  State<_ScoreDialog> createState() => _ScoreDialogState();
}

class _ScoreDialogState extends State<_ScoreDialog> {
  static const _okKey = 'interview-score-ok';
  final _field = TextEditingController();

  @override
  void dispose() {
    _field.dispose();
    super.dispose();
  }

  double? get _value {
    final v = double.tryParse(_field.text.trim().replaceAll(',', '.'));
    return v != null && v.isFinite && v >= 0 ? v : null;
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    content: TextField(
      key: const ValueKey('interview-score'),
      controller: _field,
      autofocus: true,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      decoration: const InputDecoration(prefixIcon: Icon(Icons.scoreboard)),
      onChanged: (_) => setState(() {}),
      onSubmitted: (_) => _done(),
    ),
    actions: [
      IconButton.filled(
        key: const ValueKey(_okKey),
        onPressed: _value == null ? null : _done,
        icon: Semantics(label: a11y(_okKey), child: const Icon(Icons.check)),
      ),
    ],
  );

  void _done() {
    final v = _value;
    if (v != null) Navigator.of(context).pop(v);
  }
}
