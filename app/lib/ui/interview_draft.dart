/// The interview part of the create form: toggle, test time, invite url,
/// trips or the explicit no-trip (one of the two is required). Icons only.
library;

import 'package:flutter/material.dart';
import 'package:tutor/focus/focus_models.dart';
import 'package:tutor/focus/interview_models.dart';
import 'package:tutor/model/interview_body.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/ui/interview_labels.dart';
import 'package:tutor/ui/interview_prompts.dart';

String _iso(DateTime d) => d.toIso8601String().substring(0, 10);

/// What kuhy entered for an interview project.
class InterviewDraft extends ChangeNotifier {
  /// Whether the project is an interview.
  bool on = false;

  /// The test's local date and time.
  DateTime? testAt;

  /// The invitation link (empty allowed).
  final TextEditingController url = TextEditingController();

  /// Announced trips.
  final List<Trip> trips = [];

  /// The explicit "no trip".
  bool noTrip = false;

  /// The url text changed.
  void touch() => notifyListeners();

  /// Sets the toggle.
  void toggle({required bool value}) {
    on = value;
    notifyListeners();
  }

  /// Sets the test time.
  void setTestAt(DateTime value) {
    testAt = value;
    notifyListeners();
  }

  /// Adds a trip; a trip answers the question, so it clears no-trip.
  void addTrip(DateTime start, DateTime end) {
    trips.add((start: _iso(start), end: _iso(end)));
    noTrip = false;
    notifyListeners();
  }

  /// Removes the trip at [index].
  void removeTrip(int index) {
    trips.removeAt(index);
    notifyListeners();
  }

  /// Sets no-trip; it drops the trips.
  void setNoTrip({required bool value}) {
    noTrip = value;
    if (value) trips.clear();
    notifyListeners();
  }

  /// Whether the server would take it: a test time, a trip answer, a url.
  bool get valid =>
      testAt != null && (trips.isNotEmpty || noTrip) && isWorkUrl(url.text);

  /// The test's day (the project ends on it) or null before it is set.
  DateTime? get testDay {
    final t = testAt;
    return t == null ? null : DateTime(t.year, t.month, t.day);
  }

  /// [base] as the server expects it: an interview when [on].
  RequestBody apply(RequestBody base) => !on
      ? base
      : asInterview(
          base,
          testAt: testAt!,
          inviteUrl: url.text.trim(),
          trips: List.of(trips),
          noTrip: noTrip,
        );

  @override
  void dispose() {
    url.dispose();
    super.dispose();
  }
}

/// The form rows of [draft]; [today] bounds the pickers.
List<Widget> interviewFields(
  BuildContext context,
  InterviewDraft draft,
  InterviewPrompts prompts,
  DateTime today,
) {
  final scheme = Theme.of(context).colorScheme;
  final far = today.add(const Duration(days: 365));
  final at = draft.testAt;
  return [
    Row(
      children: [
        Icon(Icons.work_outline, color: scheme.onSurfaceVariant),
        const Spacer(),
        Semantics(
          label: a11y('interview-toggle'),
          child: Switch(
            key: const ValueKey('interview-toggle'),
            value: draft.on,
            onChanged: (v) => draft.toggle(value: v),
          ),
        ),
      ],
    ),
    if (draft.on) ...[
      InkWell(
        key: const ValueKey('interview-test-at'),
        onTap: () async {
          final picked = await prompts.pickDateTime(
            context,
            first: today,
            last: far,
          );
          if (picked != null) draft.setTestAt(picked);
        },
        child: InputDecorator(
          decoration: const InputDecoration(
            prefixIcon: Icon(Icons.event),
            suffixIcon: Icon(Icons.schedule),
          ),
          child: at == null
              ? const SizedBox(height: 20)
              : Text(localMinute(at)),
        ),
      ),
      Padding(
        key: const ValueKey('interview-url'),
        padding: const EdgeInsets.only(top: 8),
        child: TextField(
          controller: draft.url,
          keyboardType: TextInputType.url,
          decoration: const InputDecoration(prefixIcon: Icon(Icons.link)),
          onChanged: (_) => draft.touch(),
        ),
      ),
      Row(
        children: [
          IconButton.filledTonal(
            key: const ValueKey('interview-trip-add'),
            icon: Semantics(
              label: a11y('interview-trip-add'),
              child: const Icon(Icons.luggage),
            ),
            onPressed: () async {
              final r = await prompts.pickRange(
                context,
                first: today,
                last: draft.testDay ?? far,
              );
              if (r != null) draft.addTrip(r.start, r.end);
            },
          ),
          Expanded(
            child: Wrap(
              spacing: 4,
              children: [
                for (var i = 0; i < draft.trips.length; i++)
                  InputChip(
                    key: ValueKey('interview-trip:${draft.trips[i].start}'),
                    label: Text(
                      '${draft.trips[i].start.substring(5)}'
                      '..${draft.trips[i].end.substring(5)}',
                    ),
                    onPressed: () => draft.removeTrip(i),
                    onDeleted: () => draft.removeTrip(i),
                  ),
              ],
            ),
          ),
          Icon(Icons.no_luggage, color: scheme.onSurfaceVariant),
          Semantics(
            label: a11y('interview-no-trip'),
            child: Switch(
              key: const ValueKey('interview-no-trip'),
              value: draft.noTrip,
              onChanged: (v) => draft.setNoTrip(value: v),
            ),
          ),
        ],
      ),
    ],
  ];
}
