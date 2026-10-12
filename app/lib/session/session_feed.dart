/// The live session as the Session screen shows it: streams `live`, then
/// `sessions/{sid}/meta` and `sessions/{sid}/msgs` of the session it names
/// (DOCS-contract §6, §9: only these narrow paths, only while visible).
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
  const new({required this.sid, this.meta, this.messages = const []});

  /// Session id.
  final String sid;

  /// `meta`, null until it arrives.
  final SessionMeta? meta;

  /// Messages in key order.
  final List<KeyedMessage> messages;

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
  /// Creates the feed over [_stream].
  new(this._stream);

  final RtdbStream _stream;

  /// What `live` says (null: no live session, or not loaded yet).
  final ValueNotifier<Live?> live = ValueNotifier(null);

  /// Whether `live` has been read at least once.
  final ValueNotifier<bool> loaded = ValueNotifier(false);

  /// The session on screen.
  final ValueNotifier<SessionView?> view = ValueNotifier(null);

  final List<StreamSubscription<RtdbEvent>> _subs = [];
  // Cancelled in stop(); the lint cannot see across methods.
  // ignore: cancel_subscriptions
  StreamSubscription<RtdbEvent>? _liveSub;
  Object? _liveTree;
  Object? _meta;
  Object? _msgs;

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
      if (next != null && isSessionId(next.session)) follow(next.session);
    });
    final shown = view.value?.sid;
    if (shown != null && _subs.isEmpty) _subscribe(shown);
  }

  /// Streams session [sid] (no-op when already on it).
  void follow(String sid) {
    if (view.value?.sid == sid && _subs.isNotEmpty) return;
    _cancelSession();
    view.value = SessionView(sid: sid);
    _subscribe(sid);
  }

  void _subscribe(String sid) {
    _meta = null;
    _msgs = null;
    final base = Paths.session(sid);
    _subs
      ..add(
        _stream.listen('$base/meta').listen((e) {
          _meta = applyEvent(_meta, e);
          _publish(sid);
        }),
      )
      ..add(
        _stream.listen('$base/msgs').listen((e) {
          _msgs = applyEvent(_msgs, e);
          _publish(sid);
        }),
      );
  }

  void _publish(String sid) {
    view.value = SessionView(
      sid: sid,
      meta: parseMeta(_meta),
      messages: parseMessages(_msgs),
    );
  }

  void _cancelSession() {
    for (final s in _subs) {
      unawaited(s.cancel());
    }
    _subs.clear();
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
