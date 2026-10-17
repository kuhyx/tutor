/// "New cards per day" (Settings): `new_cap` events in the log, so the PC
/// reads the same value. The effective cap is the latest event by `at`
/// (then eid), or [defaultNewCap] when there is none; the worker applies
/// the same rule.
library;

import 'package:tutor/model/log_event.dart';

/// The cap without any `new_cap` event.
const defaultNewCap = 25;

/// The range Settings accepts.
const minNewCap = 1;

/// The range Settings accepts.
const maxNewCap = 200;

/// The effective cap in [events].
int effectiveNewCap(Iterable<LoggedEvent> events) {
  LoggedEvent? latest;
  for (final e in events) {
    if (e.event is! NewCapEvent) continue;
    final l = latest;
    final later =
        l == null ||
        e.event.at > l.event.at ||
        (e.event.at == l.event.at && e.eid.compareTo(l.eid) > 0);
    if (later) latest = e;
  }
  return (latest?.event as NewCapEvent?)?.n ?? defaultNewCap;
}
