/// Request bodies of the `mock` kind; `op` picks the step.
library;

import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';

/// Default length of a test.
const mockMinutes = 60;

/// `start`: assemble a test of [minutes].
RequestBody mockStart(int minutes) =>
    RequestBody.raw(RequestKind.mock, {'op': 'start', 'minutes': minutes});

/// `answer`: Submit of [task]; [ts] is the client time of the tap.
RequestBody mockAnswer(String mockId, String task, String answer, int ts) =>
    RequestBody.raw(RequestKind.mock, {
      'op': 'answer',
      'mock_id': mockId,
      'task': task,
      'answer': answer,
      'ts': ts,
    });

/// `run`: the actual output of [answer] on [task], never a verdict.
RequestBody mockRun(String mockId, String task, String answer) =>
    RequestBody.raw(RequestKind.mock, {
      'op': 'run',
      'mock_id': mockId,
      'task': task,
      'answer': answer,
    });

/// `finish`: grade the test (idempotent).
RequestBody mockFinish(String mockId) =>
    RequestBody.raw(RequestKind.mock, {'op': 'finish', 'mock_id': mockId});
