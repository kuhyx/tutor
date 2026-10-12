/// Small top-level records of DOCS-contract §3, §5 and curriculum §7.
library;

import 'package:tutor/model/json.dart';

/// RTDB's server-timestamp placeholder, resolved on write.
const Json serverTimestamp = {'.sv': 'timestamp'};

/// `meta`: schema gate. The client refuses an unknown schema or a
/// `min_client` above its own version.
class SchemaMeta {
  /// Creates the record.
  const new({required this.schema, required this.minClient});

  /// Parses `meta`.
  factory fromJson(Json j) => SchemaMeta(
    schema: integer(j, 'schema'),
    minClient: integer(j, 'min_client'),
  );

  /// Layout version.
  final int schema;

  /// Oldest client version the worker still serves.
  final int minClient;

  /// Whether a client at [clientVersion] that knows [knownSchema] may run.
  bool allows({required int knownSchema, required int clientVersion}) =>
      schema == knownSchema && minClient <= clientVersion;

  /// Wire form.
  Json toJson() => {'schema': schema, 'min_client': minClient};
}

/// `rev`: change counters; refetch the catalog only when `catalog` moved.
class Revs {
  /// Creates the record.
  const new({required this.catalog, required this.stats});

  /// Parses `rev`.
  factory fromJson(Json j) =>
      Revs(catalog: intOr(j, 'catalog') ?? 0, stats: intOr(j, 'stats') ?? 0);

  /// Subjects/plans/cards revision.
  final int catalog;

  /// Stats revision.
  final int stats;

  /// Wire form.
  Json toJson() => {'catalog': catalog, 'stats': stats};
}

/// `live`: the one live session, or absent.
class Live {
  /// Creates the record.
  const new({required this.session, this.subject, this.card, this.since});

  /// Parses `live`.
  factory fromJson(Json j) => Live(
    session: str(j, 'session'),
    subject: strOr(j, 'subject'),
    card: strOr(j, 'card'),
    since: intOr(j, 'since'),
  );

  /// Session id.
  final String session;

  /// Subject id.
  final String? subject;

  /// Card id being taught.
  final String? card;

  /// Since when (ms).
  final int? since;

  /// Wire form.
  Json toJson() => compact({
    'session': session,
    'subject': subject,
    'card': card,
    'since': since,
  });
}

/// `prefs` (client-written, last writer wins).
class Prefs {
  /// Creates the record.
  const new({this.currentSubject});

  /// Parses `prefs`.
  factory fromJson(Json j) =>
      Prefs(currentSubject: strOr(j, 'current_subject'));

  /// Subject new material comes from.
  final String? currentSubject;

  /// Wire form.
  Json toJson() => compact({'current_subject': currentSubject});
}

/// `presence/workers/{dev}` heartbeat (§5).
class WorkerPresence {
  /// Creates the record.
  const new({
    required this.host,
    required this.pid,
    required this.version,
    required this.started,
    required this.beat,
    this.chatLane,
    this.buildLane,
    this.skewMs = 0,
  });

  /// Parses a heartbeat.
  factory fromJson(Json j) {
    final lanes = objOr(j, 'lanes') ?? const {};
    return WorkerPresence(
      host: str(j, 'host'),
      pid: integer(j, 'pid'),
      version: str(j, 'version'),
      started: integer(j, 'started'),
      beat: integer(j, 'beat'),
      chatLane: strOr(lanes, 'chat'),
      buildLane: strOr(lanes, 'build'),
      skewMs: intOr(j, 'skew_ms') ?? 0,
    );
  }

  /// PC host name.
  final String host;

  /// Worker pid.
  final int pid;

  /// Worker version.
  final String version;

  /// Start time (ms).
  final int started;

  /// Server time of the last beat. Never compared with the device clock.
  final int beat;

  /// rid in flight on the chat lane.
  final String? chatLane;

  /// rid in flight on the build lane.
  final String? buildLane;

  /// Measured server-vs-PC clock skew.
  final int skewMs;

  /// Wire form.
  Json toJson() => {
    'host': host,
    'pid': pid,
    'version': version,
    'started': started,
    'beat': beat,
    'lanes': compact({'chat': chatLane, 'build': buildLane}),
    'skew_ms': skewMs,
  };
}

/// `presence/clients/{dev}`.
class ClientPresence {
  /// Creates the record; a null [seen] writes the server timestamp.
  const new({required this.platform, required this.app, this.seen});

  /// Parses the record.
  factory fromJson(Json j) => ClientPresence(
    platform: str(j, 'platform'),
    app: str(j, 'app'),
    seen: intOr(j, 'seen'),
  );

  /// `android` or `web`.
  final String platform;

  /// App version.
  final String app;

  /// Server time last seen.
  final int? seen;

  /// Wire form.
  Json toJson() => {
    'platform': platform,
    'app': app,
    'seen': seen ?? serverTimestamp,
  };
}
