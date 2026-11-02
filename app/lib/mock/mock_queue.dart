/// Submits that could not reach the PC yet, as focus events do
/// (`focus/event_queue.dart`): the rid and tap time are fixed when the
/// answer is submitted, and a replay in order is harmless (the worker's
/// done-map answers a done rid again).
library;

import 'dart:async';
import 'dart:convert';

import 'package:tutor/mock/mock_requests.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/util/ulid.dart';

const _key = 'mock.answers';

/// One submitted answer waiting to be sent.
typedef QueuedAnswer = ({
  String rid,
  String mockId,
  String task,
  String answer,
  int ts,
});

/// Sends one answer under its stored rid and `ts`; true once it landed.
typedef AnswerSender = Future<bool> Function(QueuedAnswer answer);

/// The persisted, ordered queue.
class MockAnswerQueue {
  /// Creates the queue over [_kv]; tests inject [ulid] and [now] (ms).
  new(this._kv, {UlidGenerator? ulid, int Function()? now})
    : _ulid = ulid ?? UlidGenerator(),
      _now = now ?? (() => DateTime.now().millisecondsSinceEpoch);

  final KvStore _kv;
  final UlidGenerator _ulid;
  final int Function() _now;
  Future<void> _lock = Future.value();
  Future<int>? _flushing;

  /// Stores an answer of [task] with the time of the tap.
  Future<QueuedAnswer> enqueue(String mockId, String task, String answer) {
    final a = (
      rid: _ulid.next(),
      mockId: mockId,
      task: task,
      answer: answer,
      ts: _now(),
    );
    return _locked(() async {
      await _write([...await pending(), a]);
      return a;
    });
  }

  /// The queued answers, oldest first.
  Future<List<QueuedAnswer>> pending() async {
    final raw = await _kv.get(_key);
    if (raw == null) return const [];
    try {
      return [
        for (final j in jsonDecode(raw) as List<dynamic>)
          (
            rid: (j as Map<String, dynamic>)['rid'] as String,
            mockId: j['mock_id'] as String,
            task: j['task'] as String,
            answer: j['answer'] as String,
            ts: j['ts'] as int,
          ),
      ];
    } on Object {
      return const [];
    }
  }

  /// Replays the queue through [send], stopping at the first failure (order
  /// matters); resolves with how many are left. A flush running is joined.
  Future<int> flush(AnswerSender send) {
    final running = _flushing;
    if (running != null) return running;
    final run = _flush(send).whenComplete(() => _flushing = null);
    _flushing = run;
    return run;
  }

  Future<int> _flush(AnswerSender send) async {
    for (final a in await pending()) {
      if (!await send(a)) break;
      await _locked(() async {
        await _write([
          for (final p in await pending())
            if (p.rid != a.rid) p,
        ]);
      });
    }
    return (await pending()).length;
  }

  Future<void> _write(List<QueuedAnswer> all) => _kv.set(
    _key,
    jsonEncode([
      for (final a in all)
        {
          'rid': a.rid,
          'mock_id': a.mockId,
          'task': a.task,
          'answer': a.answer,
          'ts': a.ts,
        },
    ]),
  );

  Future<T> _locked<T>(Future<T> Function() body) {
    final done = _lock.then((_) => body());
    _lock = done.then<void>((_) {}, onError: (_) {});
    return done;
  }
}

/// Delivers a queued answer as `requests/{rid}/req`, same rid, tap time kept.
AnswerSender relayAnswerSender(RequestRelay relay) => (a) async {
  final body = mockAnswer(a.mockId, a.task, a.answer, a.ts);
  final req = RequestReq(
    kind: body.kind,
    dev: relay.dev,
    sentAt: a.ts,
    body: body.body,
  );
  try {
    await relay.client.put(Paths.requestReq(a.rid), req.toJson());
  } on Object {
    return false;
  }
  return true;
};
