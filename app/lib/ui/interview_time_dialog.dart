/// A time of day as digits only: hour and minute fields, a check to confirm.
/// Flutter's own time picker paints words (textgate), so interview prompts
/// use this one.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Opens the dialog: the time chosen, or null on dismiss.
Future<TimeOfDay?> showDigitTimePicker({
  required BuildContext context,
  required TimeOfDay initialTime,
}) => showDialog<TimeOfDay>(
  context: context,
  builder: (_) => DigitTimePicker(initialTime: initialTime),
);

/// The dialog; [showDigitTimePicker] opens it.
class DigitTimePicker extends StatefulWidget {
  /// Creates it holding [initialTime].
  const new({required this.initialTime, super.key});

  /// Key of the hour field.
  static const hourKey = Key('time-hour');

  /// Key of the minute field.
  static const minuteKey = Key('time-minute');

  /// Key of the confirm button.
  static const okKey = Key('time-ok');

  /// The time shown on open.
  final TimeOfDay initialTime;

  @override
  State<DigitTimePicker> createState() => _DigitTimePickerState();
}

class _DigitTimePickerState extends State<DigitTimePicker> {
  late final _hour = TextEditingController(text: '${widget.initialTime.hour}');
  late final _minute = TextEditingController(
    text: widget.initialTime.minute.toString().padLeft(2, '0'),
  );

  @override
  void dispose() {
    _hour.dispose();
    _minute.dispose();
    super.dispose();
  }

  TimeOfDay? get _value {
    final h = int.tryParse(_hour.text);
    final m = int.tryParse(_minute.text);
    if (h == null || m == null || h > 23 || m > 59) return null;
    return TimeOfDay(hour: h, minute: m);
  }

  Widget _field(Key key, TextEditingController c) => SizedBox(
    width: 64,
    child: TextField(
      key: key,
      controller: c,
      textAlign: TextAlign.center,
      keyboardType: TextInputType.number,
      inputFormatters: [
        FilteringTextInputFormatter.digitsOnly,
        LengthLimitingTextInputFormatter(2),
      ],
      onChanged: (_) => setState(() {}),
    ),
  );

  @override
  Widget build(BuildContext context) => Dialog(
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        spacing: AppSpacing.sm,
        children: [
          _field(DigitTimePicker.hourKey, _hour),
          Text(':', style: Theme.of(context).textTheme.titleLarge),
          _field(DigitTimePicker.minuteKey, _minute),
          IconButton.filled(
            key: DigitTimePicker.okKey,
            icon: const Icon(Icons.check, semanticLabel: 'Confirm'),
            onPressed: _value == null
                ? null
                : () => Navigator.of(context).pop(_value),
          ),
        ],
      ),
    ),
  );
}
