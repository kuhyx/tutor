/// The worker's half of a request: `claim` and `result` (DOCS-contract §4).
library;

import 'package:tutor/model/json.dart';
import 'package:tutor/model/request.dart' show Phase;

/// `claim` (worker-written).
class RequestClaim {
  /// Creates the record.
  const new({
    required this.by,
    required this.leaseUntil,
    required this.attempt,
    required this.phase,
    required this.at,
  });

  /// Parses `claim`.
  factory fromJson(Json j) => RequestClaim(
    by: str(j, 'by'),
    leaseUntil: integer(j, 'lease_until'),
    attempt: integer(j, 'attempt'),
    phase: Phase.parse(str(j, 'phase')),
    at: integer(j, 'at'),
  );

  /// Worker device id.
  final String by;

  /// Lease end (worker clock, ms).
  final int leaseUntil;

  /// Attempt number (>3 gives up).
  final int attempt;

  /// Current phase.
  final Phase phase;

  /// When the phase was set.
  final int at;

  /// Wire form.
  Json toJson() => {
    'by': by,
    'lease_until': leaseUntil,
    'attempt': attempt,
    'phase': phase.wire,
    'at': at,
  };
}

/// `result` (worker-written; final).
class RequestResult {
  /// Creates the record.
  const new({
    required this.ok,
    required this.at,
    this.data = const {},
    this.code,
    this.error,
    this.retry = false,
  });

  /// Parses `result`.
  factory fromJson(Json j) => RequestResult(
    ok: flag(j, 'ok'),
    at: integer(j, 'at'),
    data: objOr(j, 'data') ?? const {},
    code: strOr(j, 'code'),
    error: strOr(j, 'error'),
    retry: flag(j, 'retry'),
  );

  /// Success.
  final bool ok;

  /// When the worker finished.
  final int at;

  /// Kind-specific result data.
  final Json data;

  /// Error code (see `relay/error_text.dart`).
  final String? code;

  /// Human-readable error, shown to kuhy.
  final String? error;

  /// Whether the worker suggests retrying.
  final bool retry;

  /// Wire form.
  Json toJson() => compact({
    'ok': ok,
    'at': at,
    'data': data.isEmpty ? null : data,
    'code': code,
    'error': error,
    if (!ok) 'retry': retry,
  });
}
