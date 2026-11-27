/// Small reads/writes several screens share: `prefs`, `stats`.
library;

import 'package:tutor/model/ids.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/sync/put_outbox.dart';
import 'package:tutor/sync/rtdb_client.dart';

/// Picks the subject new material comes from (`prefs.current_subject`,
/// client-written, last writer wins): kept on this install at once and
/// pushed by [outbox] when the database answers.
Future<void> setCurrentSubject(PutOutbox outbox, String subject) async {
  if (!isSlug(subject)) throw ArgumentError.value(subject, 'subject');
  await outbox.put(currentSubjectPath, subject);
}

/// Where the picked subject lives.
const currentSubjectPath = '${Paths.prefs}/current_subject';

/// `stats`, or null when the worker has not written it yet.
Future<Stats?> fetchStats(RtdbClient client) async {
  final raw = await client.get(Paths.stats);
  return raw == null ? null : Stats.fromJson(asJson(raw, 'stats'));
}
