import 'dart:convert';

import 'package:tutor/focus/event_queue.dart';
import 'package:tutor/focus/focus_models.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/storage/kv_store.dart';

const _statusKey = 'focus.status';

/// Delivers a queued tap as `requests/{rid}/req`, same rid, tap time kept.
FocusSender relaySender(RequestRelay relay) => (e) async {
  final body = RequestBody.focusEvent(e.event, e.ts, platform: e.platform);
  final req = RequestReq(
    kind: body.kind,
    dev: relay.dev,
    sentAt: e.ts,
    body: body.body,
  );
  try {
    await relay.client.put(Paths.requestReq(e.rid), req.toJson());
  } on Object {
    return FocusSendOutcome.retry;
  }
  return FocusSendOutcome.sent;
};

/// The last `focus_status` this install saw, for opening offline.
Future<FocusStatus?> cachedStatus(KvStore kv) async {
  final raw = await kv.get(_statusKey);
  if (raw == null) return null;
  try {
    return parseStatus(asJson(jsonDecode(raw)));
  } on FormatException {
    return null;
  }
}

/// Remembers a `focus_status` result.
Future<void> cacheStatus(KvStore kv, Json data) =>
    kv.set(_statusKey, jsonEncode(data));
