/// The auto-switch: when a chat request fails with `claude_unavailable`, the
/// screen that sent it runs the outage chooser (`session/fallback_route.dart`:
/// due -> Review, else read mode, else the drill, else read mode's empty
/// glyph) in the failed request's subject (none: every subject), with the
/// "Claude limit" glyph. Watches the runner's status, so a Retry switches
/// too, not only the first send.
library;

import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/session/fallback_route.dart';

/// Starts watching [runner] for [state]'s screen; returns the stop callback
/// (call it before the runner is disposed).
VoidCallback switchToDrillOnLimit(
  State state,
  TutorServices services,
  RequestRunner runner,
) {
  RelayStatus? seen;
  void check() {
    final status = runner.status.value;
    // Once per failure: the same status object may be announced twice.
    if (status is! RelayFailed ||
        status.code != claudeUnavailable ||
        identical(status, seen) ||
        !state.mounted) {
      return;
    }
    seen = status;
    final subject = runner.lastBody?.body['subject'];
    unawaited(
      openFallback(
        state.context,
        services,
        subject: subject is String ? subject : null,
        unavailable: status.unavailable,
      ),
    );
  }

  runner.status.addListener(check);
  return () => runner.status.removeListener(check);
}
