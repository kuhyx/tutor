import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:tutor/mock/mock_models.dart';
import 'package:tutor/mock/mock_queue.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/storage/kv_store.dart';

const _key = 'mock.active';

int _wall() => DateTime.now().millisecondsSinceEpoch;

/// Forgets the saved test.
Future<void> discardMockSession(KvStore kv) => kv.remove(_key);

/// The saved test, or null when none is stored or it cannot be read.
Future<MockSession?> loadMockSession(
  KvStore kv,
  MockAnswerQueue queue,
  AnswerSender send, {
  int Function()? now,
}) async {
  final raw = await kv.get(_key);
  if (raw == null) return null;
  try {
    final j = asJson(jsonDecode(raw));
    final paper = asJson(j['paper']);
    final result = objOr(j, 'result');
    return MockSession._(
      kv,
      queue,
      send,
      parsePaper(paper),
      now ?? _wall,
      rawPaper: paper,
      answers: mapOf(j, 'answers', (v) => '$v'),
      submitted: mapOf(j, 'submitted', (v) => '$v'),
      index: intOr(j, 'index') ?? 0,
      result: result == null ? null : parseResult(result),
      rawResult: result,
    );
  } on FormatException {
    await discardMockSession(kv);
    return null;
  }
}

/// The test in progress, saved on every change; the clock is wall time.
class MockSession extends ChangeNotifier {
  /// Starts a test from a `start` result.
  factory begin(
    KvStore kv,
    MockAnswerQueue queue,
    AnswerSender send,
    Json rawPaper, {
    int Function()? now,
  }) => MockSession._(
    kv,
    queue,
    send,
    parsePaper(rawPaper),
    now ?? _wall,
    rawPaper: rawPaper,
  );

  new _(
    this._kv,
    this._queue,
    this._send,
    this.paper,
    this._now, {
    required this._rawPaper,
    Map<String, String>? answers,
    Map<String, String>? submitted,
    this.index = 0,
    this.result,
    this._rawResult,
  }) : answers = {...?answers},
       _submitted = {...?submitted};

  final KvStore _kv;
  final MockAnswerQueue _queue;
  final AnswerSender _send;
  final int Function() _now;
  final Json _rawPaper;
  final Map<String, String> _submitted;
  Json? _rawResult;

  /// Tasks and clock.
  final MockPaper paper;

  /// Typed or picked text per task id.
  final Map<String, String> answers;

  /// Task on screen.
  int index;

  /// Graded test, once finished.
  MockResult? result;

  /// Time left; zero once over.
  Duration get remaining {
    final ms = paper.deadlineMs - _now();
    return Duration(milliseconds: ms < 0 ? 0 : ms);
  }

  /// Whether [id]'s text is what was last submitted.
  bool isSubmitted(String id) =>
      _submitted.containsKey(id) && _submitted[id] == answers[id];

  /// Shows task [go]; keeps typed [text] of task [id].
  void update({int? go, String? id, String? text}) {
    if (go != null) index = go.clamp(0, paper.tasks.length - 1);
    if (id != null && text != null) answers[id] = text;
    _changed();
  }

  /// Queues [id]'s answer with the tap time; sent when it can be.
  Future<void> submit(String id) async {
    final text = answers[id] ?? '';
    if (text.trim().isEmpty) return;
    _submitted[id] = text;
    _changed();
    await _queue.enqueue(paper.mockId, id, text);
    unawaited(_queue.flush(_send));
  }

  /// Submits every typed answer, sends the queue; true when none waits.
  Future<bool> settle() async {
    for (final t in paper.tasks) {
      if (!isSubmitted(t.id)) await submit(t.id);
    }
    final left = await _queue.flush(_send);
    return left == 0;
  }

  /// Keeps the graded [data].
  void finished(Json data) {
    _rawResult = data;
    result = parseResult(data);
    _changed();
  }

  void _changed() {
    notifyListeners();
    unawaited(
      _kv.set(
        _key,
        jsonEncode({
          'paper': _rawPaper,
          'answers': answers,
          'submitted': _submitted,
          'index': index,
          'result': ?_rawResult,
        }),
      ),
    );
  }
}
