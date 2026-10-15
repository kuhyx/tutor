import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/relay/request_relay.dart';

import '../support/drill.dart';

String _hhmm(int unixSeconds) {
  final t = DateTime.fromMillisecondsSinceEpoch(unixSeconds * 1000);
  return '${t.hour.toString().padLeft(2, '0')}:'
      '${t.minute.toString().padLeft(2, '0')}';
}

void main() {
  const at = 1792000000;

  test('banner: local HH:MM; no reason reads Claude unavailable', () {
    expect(
      const Unavailable(until: at, reason: 'five_hour_limit').banner,
      'Claude limit — back at ${_hhmm(at)}',
    );
    expect(
      const Unavailable(until: at).banner,
      'Claude unavailable — back at ${_hhmm(at)}',
    );
    expect(const Unavailable(reason: '  ').banner, 'Claude unavailable');
    expect(const Unavailable(reason: 'limit').banner, 'Claude limit');
    // Minutes and hours are zero-padded.
    final early = DateTime(2026, 10, 15, 3, 5).millisecondsSinceEpoch ~/ 1000;
    expect(Unavailable(until: early, reason: 'x').banner, endsWith('03:05'));
  });

  test('Unavailable parses the drill shape and the error body', () {
    final j = Unavailable.fromJson({'until': at, 'reason': 'limit'});
    expect((j.until, j.reason), (at, 'limit'));
    final top = Unavailable.fromError({'resets_at': at, 'reason': 'r'});
    expect((top.until, top.reason), (at, 'r'));
    final nested = Unavailable.fromError({
      'data': {'resets_at': at.toDouble(), 'reason': 'r'},
    });
    expect((nested.until, nested.reason), (at, 'r'));
    final bare = Unavailable.fromError({'data': 'odd', 'reason': 7});
    expect((bare.until, bare.reason), (null, null));
  });

  test('drill_next: question, empty, unavailable', () {
    final q = DrillNext.fromJson(
      drillQuestion(unavailable: {'until': at, 'reason': 'limit'}),
    ) as DrillQuestion;
    expect(q.promptId, 'p1');
    expect(q.card.front, 'What does the crankshaft do?');
    expect(q.options, hasLength(3));
    expect((q.today.activeMin, q.today.creditedMin), (31, 23));
    expect(q.unavailable?.until, at);
    expect(DrillNext.fromJson({'empty': true}), isA<DrillEmpty>());
    final plain = DrillNext.fromJson(drillQuestion()) as DrillQuestion;
    expect(plain.unavailable, isNull);
    expect(
      () => DrillNext.fromJson({
        ...drillQuestion(),
        'options': [1, 2],
      }),
      throwsFormatException,
    );
  });

  test('drill_answer and anki_status', () {
    final a = DrillAnswer.fromJson(drillGrade(1));
    expect((a.correct, a.answerIndex, a.minuteCredited), (true, 1, true));
    expect(a.today.creditedMin, 24);
    expect(DrillAnswer.fromJson(drillGrade(0)).correct, isFalse);
    final s = AnkiStatus.fromJson({
      ...ankiStatus(5),
      'last_sync_at': at,
      'unavailable': {'until': at},
    });
    expect((s.creditedTodayMin, s.eligibleTodayMin, s.lastSyncAt), (5, 12, at));
    expect(s.unavailable?.until, at);
    expect(AnkiStatus.fromJson(ankiStatus(0)).unavailable, isNull);
  });

  test('request kinds and bodies', () {
    final next = RequestBody.drillNext(subject: 'car');
    expect(next.kind.wire, 'drill_next');
    expect(next.body, {'subject': 'car'});
    final pick = RequestBody.drillAnswer('p1', 2);
    expect(pick.kind.wire, 'drill_answer');
    expect(pick.body, {'prompt_id': 'p1', 'choice': 2});
    expect(RequestBody.ankiStatus().kind, RequestKind.ankiStatus);
    expect(RequestKind.parse('anki_status'), RequestKind.ankiStatus);
    expect(RequestKind.drillNext.lane, Lane.chat);
  });

  test('claude_unavailable result carries resets_at and reason', () {
    final status = statusOf({
      'result': {
        'ok': false,
        'at': 1,
        'code': claudeUnavailable,
        'error': 'limit',
        'resets_at': at,
        'reason': 'five_hour_limit',
      },
    }) as RelayFailed;
    expect(status.code, 'claude_unavailable');
    expect(status.text, contains('Claude is not available'));
    expect(status.unavailable?.until, at);
    expect(status.unavailable?.reason, 'five_hour_limit');
    final other = statusOf({
      'result': {'ok': false, 'at': 1, 'code': 'model_error'},
    }) as RelayFailed;
    expect(other.unavailable, isNull);
  });
}
