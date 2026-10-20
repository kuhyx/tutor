/// The live session as the Session screen shows it: streams `live`, then
/// `sessions/{sid}` of the session it names, ONE listen whose `put`/`patch`
/// paths fold into `meta`, `msgs` and `progress` (DOCS-contract §6, §9: only
/// while visible). RTDB speaks HTTP/1.1, so every listen holds one of the
/// browser's 6 connections to it; three listens per session left none for
/// a Send's PUT (2026-10-20). A reconnect resends the whole session.
///
/// When `live` turns null (after Stop here) the last session stays on screen,
/// read-only, as the web page keeps its hash on the stopped session.
library;

import 'dart:async';
import 'dart:developer';

import 'package:flutter/foundation.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/model/root.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/model/trace.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/sync/rtdb_stream.dart';

/// A message with its RTDB key (`m0007`).
class KeyedMessage {
  /// Creates the pair.
  const new(this.key, this.message);

  /// `m%04d` key.
  final String key;

  /// The message.
  final Message message;
}

/// One session's projection.
class SessionView {
  /// Creates the view.
  const new({
    required this.sid,
    this.meta,
    this.messages = const [],
    this.progress,
  });

  /// Session id.
  final String sid;

  /// `meta`, null until it arrives.
  final SessionMeta? meta;

  /// Messages in key order.
  final List<KeyedMessage> messages;

  /// `progress`: the trace of the request in flight, if any.
  final LiveProgress? progress;

  /// The latest message, if any.
  KeyedMessage? get last => messages.isEmpty ? null : messages.last;
}

/// Parses a `msgs` node into key-ordered messages, skipping malformed ones.
List<KeyedMessage> parseMessages(Object? node) {
  if (node is! Map<String, dynamic>) return const [];
  final out = <KeyedMessage>[];
  for (final key in node.keys.where(isMessageKey).toList()..sort()) {
    try {
      out.add(KeyedMessage(key, Message.fromJson(asJson(node[key], key))));
    } on FormatException catch (error) {
      log('skipping malformed message $key', level: 900, error: error);
    }
  }
  return out;
}

/// Parses a `meta` node; null when absent or malformed.
SessionMeta? parseMeta(Object? node) {
  if (node is! Map<String, dynamic>) return null;
  try {
    return SessionMeta.fromJson(node);
  } on FormatException catch (error) {
    log('malformed session meta', level: 900, error: error);
    return null;
  }
}

/// Follows the live session.
class SessionFeed {
  /// Creates the feed over [_stream]; with [subject] it follows `live` only
  /// while `live` is a session of that subject.
  new(this._stream, {this.subject});

  final RtdbStream _stream;

  /// The subject whose live session is followed (null: any).
  final String? subject;

  /// What `live` says (null: no live session, or not loaded yet).
  final ValueNotifier<Live?> live = ValueNotifier(null);

  /// Whether `live` has been read at least once.
  final ValueNotifier<bool> loaded = ValueNotifier(false);

  /// The session on screen.
  final ValueNotifier<SessionView?> view = ValueNotifier(null);

  // Cancelled in stop(); the lint cannot see across methods.
  // ignore: cancel_subscriptions
  StreamSubscription<RtdbEvent>? _sessionSub;
  // Cancelled in stop(), as above.
  // ignore: cancel_subscriptions
  StreamSubscription<RtdbEvent>? _liveSub;
  Object? _liveTree;
  Object? _session;

  /// Starts streaming `live` (idempotent). After [stop], the session that
  /// was on screen is re-followed from a fresh snapshot.
  void start() {
    if (_liveSub != null) return;
    _liveSub = _stream.listen(Paths.live).listen((event) {
      if (event is! RtdbPut && event is! RtdbPatch) return;
      _liveTree = applyEvent(_liveTree, event);
      final tree = _liveTree;
      Live? next;
      try {
        next = tree is Json ? Live.fromJson(tree) : null;
      } on FormatException catch (error) {
        log('malformed live', level: 900, error: error);
      }
      live.value = next;
      loaded.value = true;
      if (next != null && isSessionId(next.session) && _mine(next)) {
        follow(next.session);
      }
    });
    final shown = view.value?.sid;
    if (shown != null && _sessionSub == null) _subscribe(shown);
  }

  bool _mine(Live live) => subject == null || live.subject == subject;

  /// Streams session [sid] (no-op when already on it).
  void follow(String sid) {
    if (view.value?.sid == sid && _sessionSub != null) return;
    _cancelSession();
    _session = null;
    view.value = SessionView(sid: sid);
    _subscribe(sid);
  }

  void _subscribe(String sid) {
    _sessionSub = _stream.listen(Paths.session(sid)).listen((e) {
      // `receipts` and `user` ride along; nothing here reads them.
      _session = applyEvent(_session, e);
      _publish(sid);
    });
  }

  void _publish(String sid) {
    final tree = _session;
    view.value = SessionView(
      sid: sid,
      meta: parseMeta(getAt(tree, 'meta')),
      messages: parseMessages(getAt(tree, 'msgs')),
      // The turn's thinking / research, live (DOCS-contract §6).
      progress: LiveProgress.parse(getAt(tree, 'progress')),
    );
  }

  void _cancelSession() {
    final sub = _sessionSub;
    _sessionSub = null;
    unawaited(sub?.cancel());
  }

  /// Stops every listen (screen hidden); the view is kept as last known.
  Future<void> stop() async {
    _cancelSession();
    final sub = _liveSub;
    _liveSub = null;
    _liveTree = null;
    await sub?.cancel();
  }

  /// Releases the notifiers.
  Future<void> dispose() async {
    await stop();
    live.dispose();
    loaded.dispose();
    view.dispose();
  }
}
