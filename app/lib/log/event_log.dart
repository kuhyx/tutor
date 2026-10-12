/// The offline event log (curriculum §4): reviews and flags are recorded
/// locally first, PUT to `log/{own dev}/{eid}` in eid order when online,
/// and every device's events are pulled incrementally.
///
/// PUT of the same event to the same path is idempotent, so a flush that
/// dies halfway is simply run again. This device never writes another
/// device's subtree.
library;

import 'dart:convert';
import 'dart:developer';

import 'package:tutor/model/ids.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/rtdb_client.dart';
import 'package:tutor/util/ulid.dart';

const _queueKey = 'log.queue';
String _eventsKey(String dev) => 'log.events.$dev';
String _cursorKey(String dev) => 'log.cursor.$dev';
const _devicesKey = 'log.devices';

/// Local queue + per-device event cache, synced with RTDB.
class EventLog {
  /// Creates the log for device [dev].
  new({
    required this.client,
    required this.kv,
    required this.dev,
    required this.ulid,
  });

  /// REST client.
  final RtdbClient client;

  /// Local persistence.
  final KvStore kv;

  /// This install's device id.
  final String dev;

  /// eid source (monotonic, so queue order is creation order).
  final UlidGenerator ulid;

  Future<Json> _readMap(String key) async {
    final raw = await kv.get(key);
    return raw == null ? <String, dynamic>{} : asJson(jsonDecode(raw));
  }

  Future<void> _writeMap(String key, Json map) => kv.set(key, jsonEncode(map));

  /// Queues [event] locally; it counts in [all] at once, online or not.
  Future<LoggedEvent> record(LogEvent event) async {
    final eid = ulid.next();
    final queue = await _readMap(_queueKey);
    queue[eid] = event.toJson();
    await _writeMap(_queueKey, queue);
    return LoggedEvent(dev: dev, eid: eid, event: event);
  }

  /// Events still waiting to be written.
  Future<int> pending() async => (await _readMap(_queueKey)).length;

  /// PUTs queued events in eid order; returns how many were written.
  ///
  /// Throws the first [RtdbError]; everything written before it is already
  /// moved out of the queue, so calling again resumes where it stopped.
  Future<int> flush() async {
    final queue = await _readMap(_queueKey);
    final own = await _readMap(_eventsKey(dev));
    var written = 0;
    for (final eid in queue.keys.toList()..sort()) {
      await client.put(Paths.logEvent(dev, eid), queue[eid]);
      own[eid] = queue.remove(eid);
      await _writeMap(_eventsKey(dev), own);
      await _writeMap(_queueKey, queue);
      written++;
    }
    return written;
  }

  /// Pulls new events of every device (own included, which repairs a lost
  /// local cache): a shallow listing, then per device only keys after its
  /// cursor.
  Future<void> pull() async {
    final devices = (await client.keys(Paths.log)).where(isDeviceId).toList();
    await kv.set(_devicesKey, jsonEncode(devices));
    for (final d in devices) {
      final cursor = await kv.get(_cursorKey(d));
      final fetched = await client.get(
        Paths.logOf(d),
        query: cursor == null ? const {} : keyRangeQuery(cursor),
      );
      if (fetched is! Map<String, dynamic>) continue;
      final store = await _readMap(_eventsKey(d))
        ..addAll(fetched);
      await _writeMap(_eventsKey(d), store);
      final last = (fetched.keys.toList()..sort()).last;
      await kv.set(_cursorKey(d), last);
    }
  }

  /// Every known event: pulled and flushed ones of all devices, plus this
  /// device's queue. Malformed remote events are skipped (and logged):
  /// RTDB content is untrusted and one bad node must not stop reviews.
  Future<List<LoggedEvent>> all() async {
    final raw = await kv.get(_devicesKey);
    final devices = {
      dev,
      if (raw != null) ...(jsonDecode(raw) as List).cast<String>(),
    };
    final out = <LoggedEvent>[];
    void add(String d, Json events) {
      for (final MapEntry(:key, :value) in events.entries) {
        try {
          out.add(
            LoggedEvent(dev: d, eid: key, event: LogEvent.fromJson(value)),
          );
        } on FormatException catch (error) {
          log('skipping malformed log/$d/$key', level: 900, error: error);
        }
      }
    }

    for (final d in devices) {
      add(d, await _readMap(_eventsKey(d)));
    }
    add(dev, await _readMap(_queueKey));
    return out;
  }
}
