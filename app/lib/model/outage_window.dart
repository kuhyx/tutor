/// `stats.today.unavailable`: the open Claude outage window the worker
/// republishes on its stats tick (DOCS-contract-curriculum.md §7).
library;

import 'package:tutor/model/codes.dart';
import 'package:tutor/model/json.dart';

/// Claude is out until [until], for [reason].
class OutageWindow {
  /// Creates the window.
  const new({required this.until, required this.reason});

  /// Parses `{"until": <unix s>, "reason"}`; a missing or unknown reason
  /// is [UnavailableReason.other].
  factory fromJson(Json j) => OutageWindow(
    until: integer(j, 'until'),
    reason: UnavailableReason.parse(j['reason']),
  );

  /// Unix seconds when Claude is back.
  final int until;

  /// Why, in the closed vocabulary.
  final UnavailableReason reason;

  /// Still open at [now]: a past [until] is clear (the tick republishes
  /// the node only every few minutes).
  bool openAt(DateTime now) => now.millisecondsSinceEpoch < until * 1000;

  /// Wire form.
  Json toJson() => {'until': until, 'reason': reason.wire};
}
