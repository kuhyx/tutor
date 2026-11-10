/// Request bodies of the interview projects (DOCS-contract-focus.md,
/// "Interview projects"). Kept apart from `request_body.dart`, which a plain
/// focus project never needs: a `focus` create carries none of these fields.
library;

import 'package:tutor/focus/interview_models.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';

/// The proof that a chunked upload is complete (DOCS-contract §3).
typedef UploadRef = ({String upload, int chunks, String sha256, String mime});

/// Most trips one create may carry.
const int maxTrips = 20;

String _two(int n) => n.toString().padLeft(2, '0');

/// Naive local `YYYY-MM-DDTHH:MM`.
String localMinute(DateTime t) =>
    '${t.year.toString().padLeft(4, '0')}-${_two(t.month)}-${_two(t.day)}'
    'T${_two(t.hour)}:${_two(t.minute)}';

/// A `focus_create` [base] made an interview project. Exactly one of
/// [trips] (non-empty) and [noTrip] is allowed: RTDB drops an empty list,
/// so `no_trip` is the explicit "none".
RequestBody asInterview(
  RequestBody base, {
  required DateTime testAt,
  required String inviteUrl,
  List<Trip> trips = const [],
  bool noTrip = false,
}) {
  if (trips.isEmpty == !noTrip) {
    throw ArgumentError('send trips or no_trip, exactly one');
  }
  if (trips.length > maxTrips) {
    throw ArgumentError.value(trips.length, 'trips', 'at most $maxTrips');
  }
  return RequestBody.raw(base.kind, {
    ...base.body,
    'kind': 'interview',
    'test_at': localMinute(testAt),
    'invite_url': inviteUrl,
    if (trips.isNotEmpty)
      'trips': [
        for (final t in trips) {'start': t.start, 'end': t.end},
      ],
    if (noTrip) 'no_trip': true,
  });
}

/// `focus_evidence` for [milestone]; [kind] is `file` (with [upload]),
/// `tap`, `score` (number [value]), `slot` (datetime text) or `slot_confirm`.
RequestBody focusEvidence({
  required String id,
  required String milestone,
  required String kind,
  Object? value,
  UploadRef? upload,
}) => RequestBody.raw(RequestKind.focusEvidence, {
  'id': id,
  'milestone': milestone,
  'kind': kind,
  'value': ?value,
  if (upload != null) ...{
    'upload': upload.upload,
    'chunks': upload.chunks,
    'sha256': upload.sha256,
    'mime': upload.mime,
  },
});

/// `focus_trip`: announce a trip (inclusive days).
RequestBody focusTrip(String id, String start, String end) => RequestBody.raw(
  RequestKind.focusTrip,
  {'id': id, 'start': start, 'end': end},
);

/// `focus_weekend`: answer the trip question of one Saturday.
RequestBody focusWeekend(String id, String saturday, {required bool trip}) =>
    RequestBody.raw(RequestKind.focusWeekend, {
      'id': id,
      'saturday': saturday,
      'trip': trip,
    });
