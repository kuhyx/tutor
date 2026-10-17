/// "New cards per day" (Home's ⋮ menu): the effective cap from the event
/// log, saved as a `new_cap` event (1..200) that syncs to the PC, which
/// applies it to `daily_new_cap` and writes it back as `stats.new_cap`.
library;

import 'dart:async';
import 'dart:developer';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/log/new_cap.dart';
import 'package:tutor/model/log_event.dart';

/// Opens the setting over [context]'s route.
Future<void> showNewCap(BuildContext context, EventLog events) async {
  final now = effectiveNewCap(await events.all());
  if (!context.mounted) return;
  await showDialog<void>(
    context: context,
    builder: (_) => NewCapDialog(events: events, current: now),
  );
}

/// The number field.
class NewCapDialog extends StatefulWidget {
  /// Creates the dialog showing [current].
  const new({required this.events, required this.current, super.key});

  /// Where the setting goes.
  final EventLog events;

  /// The effective cap now.
  final int current;

  @override
  State<NewCapDialog> createState() => _NewCapDialogState();
}

class _NewCapDialogState extends State<NewCapDialog> {
  late final _text = TextEditingController(text: '${widget.current}');
  String? _error;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final n = int.tryParse(_text.text.trim());
    if (n == null || n < minNewCap || n > maxNewCap) {
      setState(() => _error = 'A number from $minNewCap to $maxNewCap');
      return;
    }
    if (n != widget.current) {
      final at = DateTime.now().millisecondsSinceEpoch;
      await widget.events.record(NewCapEvent(n: n, at: at));
      try {
        await widget.events.flush();
      } on Object catch (error) {
        // `on Object`: offline is normal; the event stays queued and the
        // next flush (Home load, a review) sends it.
        log('new_cap flush failed; kept queued', level: 800, error: error);
      }
    }
    if (mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('New cards per day'),
    content: Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: _text,
          autofocus: true,
          keyboardType: TextInputType.number,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          decoration: InputDecoration(labelText: 'Cards', errorText: _error),
          onSubmitted: (_) => unawaited(_save()),
        ),
        const SizedBox(height: AppSpacing.sm),
        Text(
          'Now ${widget.current} a day. Reviews never count. '
          'Learn more anyway still lifts it for one day.',
        ),
      ],
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.of(context).pop(),
        child: const Text('Cancel'),
      ),
      FilledButton(onPressed: _save, child: const Text('Save')),
    ],
  );
}
