/// A stand-in PC worker for the screenshot build: answers the model-free
/// kinds (`drill_next`, `drill_answer`, `anki_status`) from a few car
/// cards, and every other kind with an empty success. With `?claude=out`
/// the Claude kinds fail with `claude_unavailable` (resets in 95 minutes)
/// and drill questions carry `unavailable`, as the real worker will.
library;

import 'package:tutor/model/json.dart';

typedef _Q = ({
  String front,
  List<String> options,
  int answer,
  String back,
  String excerpt,
});

const List<_Q> _questions = [
  (
    front: 'What does the crankshaft do?',
    options: [
      'Opens and closes the valves',
      'Turns the pistons’ up-and-down motion into rotation',
      'Mixes fuel with air',
      'Cools the cylinder walls',
    ],
    answer: 1,
    back: 'It converts the pistons’ reciprocating motion into rotation.',
    excerpt:
        'The crankshaft translates reciprocating motion of the pistons '
        'into rotational motion.',
  ),
  (
    front: 'What are the four strokes?',
    options: [
      'Intake, compression, combustion, exhaust',
      'Ignition, injection, cooling, exhaust',
      'Suction, spark, lift, drop',
    ],
    answer: 0,
    back: 'Intake, compression, combustion (power) and exhaust.',
    excerpt:
        'The four strokes are intake, compression, combustion and exhaust, '
        'repeated twice per crankshaft revolution pair.',
  ),
];

const _source = 'https://en.wikipedia.org/wiki/Four-stroke_engine';

/// Answers a request of a kind with its `result` node; [now] is unix
/// seconds, so `resets_at` is stable per run.
Json Function(String kind, Json body) fixtureWorker({
  required bool claudeOut,
  required int now,
}) {
  var asked = 0;
  var credited = 23;
  Json today() => {'active_min': 31, 'credited_min': credited};
  Json? out() =>
      claudeOut ? {'until': now + 95 * 60, 'reason': 'five_hour_limit'} : null;
  Json ok(Json data) => {'ok': true, 'at': now * 1000, 'data': data};
  return (kind, body) {
    switch (kind) {
      case 'drill_next':
        final i = asked++ % _questions.length;
        final q = _questions[i];
        return ok({
          'prompt_id': 'p$i',
          'card': {'subject': 'car', 'id': 'eng-$i', 'front': q.front},
          'options': q.options,
          'today': today(),
          'unavailable': ?out(),
        });
      case 'drill_answer':
        final q = _questions[int.parse('${body['prompt_id']}'.substring(1))];
        final right = body['choice'] == q.answer;
        if (right) credited++;
        return ok({
          'correct': right,
          'answer_index': q.answer,
          'back': q.back,
          'excerpt': q.excerpt,
          'source': _source,
          'minute_credited': right,
          'today': today(),
        });
      case 'anki_status':
        return ok({
          'credited_today_min': 4,
          'eligible_today_min': 12,
          'last_sync_at': now,
        });
      case _ when claudeOut:
        return {
          'ok': false,
          'at': now * 1000,
          'code': 'claude_unavailable',
          'error': 'Claude is rate limited.',
          'resets_at': now + 95 * 60,
          'reason': 'five_hour_limit',
        };
      default:
        return ok({});
    }
  };
}
