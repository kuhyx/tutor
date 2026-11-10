/// A date picker that paints digits only: Flutter's own picker paints month
/// and weekday words (textgate). Month and year as numbers, ‹ › between
/// months, a Monday-first day grid with no weekday header, ✓ and ✕.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/widgets/date_num.dart';

DateTime _day(DateTime d) => DateTime(d.year, d.month, d.day);

DateTime _monthOf(DateTime d) => DateTime(d.year, d.month);

/// Opens the picker as a dialog: the picked day, or null on ✕ / dismiss.
/// [initialDate] outside [firstDate]..[lastDate] opens on the nearest edge.
Future<DateTime?> showNumericDatePicker({
  required BuildContext context,
  required DateTime initialDate,
  required DateTime firstDate,
  required DateTime lastDate,
}) => showDialog<DateTime>(
  context: context,
  builder: (_) => NumericDatePicker(
    initialDate: initialDate,
    firstDate: firstDate,
    lastDate: lastDate,
  ),
);

/// The picker dialog; [showNumericDatePicker] opens it.
class NumericDatePicker extends StatefulWidget {
  /// Creates the picker over [firstDate]..[lastDate] (whole days).
  const new({
    required this.initialDate,
    required this.firstDate,
    required this.lastDate,
    super.key,
  });

  /// Holds the month and year digits (tests look inside it).
  static const headerKey = Key('numeric-date-picker-header');

  /// The day selected on open.
  final DateTime initialDate;

  /// The earliest pickable day.
  final DateTime firstDate;

  /// The latest pickable day.
  final DateTime lastDate;

  @override
  State<NumericDatePicker> createState() => _NumericDatePickerState();
}

class _NumericDatePickerState extends State<NumericDatePicker> {
  late final DateTime _first = _day(widget.firstDate);
  late final DateTime _last = _day(widget.lastDate);
  late DateTime _selected = _clamp(_day(widget.initialDate));
  late DateTime _month = _monthOf(_selected);

  DateTime _clamp(DateTime d) =>
      d.isBefore(_first) ? _first : (d.isAfter(_last) ? _last : d);

  bool _inRange(DateTime d) => !d.isBefore(_first) && !d.isAfter(_last);

  bool get _hasPrev => _month.isAfter(_monthOf(_first));

  bool get _hasNext => _month.isBefore(_monthOf(_last));

  void _shift(int months) =>
      setState(() => _month = DateTime(_month.year, _month.month + months));

  Widget _arrow(
    IconData icon,
    String spoken, {
    required bool on,
    required int by,
  }) => IconButton(
    icon: Icon(icon, semanticLabel: spoken),
    onPressed: on ? () => _shift(by) : null,
  );

  Widget _header(TextTheme text) => Row(
    key: NumericDatePicker.headerKey,
    children: [
      _arrow(Icons.chevron_left, 'Previous month', on: _hasPrev, by: -1),
      Expanded(
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          spacing: AppSpacing.md,
          children: [
            Text('${_month.month}', style: text.titleLarge),
            Text('${_month.year}', style: text.titleLarge),
          ],
        ),
      ),
      _arrow(Icons.chevron_right, 'Next month', on: _hasNext, by: 1),
    ],
  );

  Widget _grid() {
    final days = DateUtils.getDaysInMonth(_month.year, _month.month);
    // Monday = column 0; DateTime.weekday is 1 (Mon) .. 7 (Sun).
    final lead = _month.weekday - 1;
    final cells = <Widget>[
      for (var i = 0; i < lead; i++)
        const SizedBox.square(dimension: DayCell.size),
      for (var d = 1; d <= days; d++)
        _cell(DateTime(_month.year, _month.month, d)),
    ];
    while (cells.length % 7 != 0) {
      cells.add(const SizedBox.square(dimension: DayCell.size));
    }
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var r = 0; r < cells.length; r += 7)
          Row(
            mainAxisSize: MainAxisSize.min,
            children: cells.sublist(r, r + 7),
          ),
      ],
    );
  }

  Widget _cell(DateTime d) => DayCell(
    date: d,
    enabled: _inRange(d),
    selected: d == _selected,
    onTap: () => setState(() => _selected = d),
  );

  @override
  Widget build(BuildContext context) => Dialog(
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: DayCell.size * 7,
            child: _header(Theme.of(context).textTheme),
          ),
          const SizedBox(height: AppSpacing.sm),
          _grid(),
          const SizedBox(height: AppSpacing.sm),
          SizedBox(
            width: DayCell.size * 7,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.end,
              spacing: AppSpacing.sm,
              children: [
                IconButton(
                  icon: const Icon(Icons.close, semanticLabel: 'Cancel'),
                  onPressed: () => Navigator.of(context).pop(),
                ),
                IconButton.filled(
                  icon: const Icon(Icons.check, semanticLabel: 'Confirm'),
                  onPressed: () => Navigator.of(context).pop(_selected),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}

/// One day of the grid: its number, filled when [selected], dimmed and dead
/// when not [enabled].
class DayCell extends StatelessWidget {
  /// Creates the cell.
  const new({
    required this.date,
    required this.enabled,
    required this.selected,
    required this.onTap,
    super.key,
  });

  /// Side of a cell in logical pixels.
  static const double size = 44;

  /// The day this cell picks.
  final DateTime date;

  /// Day of the month, as painted.
  int get day => date.day;

  /// Inside the pickable range.
  final bool enabled;

  /// The picked day.
  final bool selected;

  /// Picks this day (ignored when not [enabled]).
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final fg = selected
        ? scheme.onPrimary
        : enabled
        ? scheme.onSurface
        : scheme.onSurface.withValues(alpha: 0.38);
    return SizedBox.square(
      dimension: size,
      child: Semantics(
        // Spoken as the whole date (TalkBack, E2E); painted as the day only.
        label: isoDate(date),
        excludeSemantics: true,
        button: true,
        enabled: enabled,
        selected: selected,
        // excludeSemantics drops the InkWell's tap: give it back here.
        onTap: enabled ? onTap : null,
        child: InkWell(
          customBorder: const CircleBorder(),
          onTap: enabled ? onTap : null,
          child: DecoratedBox(
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: selected ? scheme.primary : null,
            ),
            child: Center(
              child: Text('$day', style: TextStyle(color: fg)),
            ),
          ),
        ),
      ),
    );
  }
}
