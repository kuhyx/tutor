/// Feeds each successful result, also one a Retry delivers, to a callback.
library;

import 'package:flutter/foundation.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';

/// Calls [onData] once per new `RelayDone` of [runner]; returns the stop.
VoidCallback listenDone(RequestRunner runner, ValueChanged<Json> onData) {
  RelayStatus? last;
  void check() {
    final s = runner.status.value;
    if (s is RelayDone && !identical(s, last)) {
      last = s;
      onData(s.data);
    }
  }

  runner.status.addListener(check);
  return () => runner.status.removeListener(check);
}
