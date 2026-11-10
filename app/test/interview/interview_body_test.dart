import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/interview_body.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';

RequestBody _base() => RequestBody.focusCreate(
  name: 'Acme',
  start: '2026-11-10',
  end: '2026-11-20',
  replaces: const ['leetcode'],
  dailyMinutes: 30,
  unlockMinutes: 30,
  subjects: const ['automation'],
  sitePatterns: const [],
  workUrl: '',
);

void main() {
  test('the new kinds exist on the chat lane with their wire names', () {
    expect(RequestKind.focusEvidence.wire, 'focus_evidence');
    expect(RequestKind.focusTrip.wire, 'focus_trip');
    expect(RequestKind.focusWeekend.wire, 'focus_weekend');
    for (final k in [
      RequestKind.focusEvidence,
      RequestKind.focusTrip,
      RequestKind.focusWeekend,
    ]) {
      expect(k.lane, Lane.chat);
      expect(RequestKind.parse(k.wire), k);
    }
  });

  test('a plain focus create is unchanged: no interview fields at all', () {
    final body = _base().body;
    for (final k in ['kind', 'test_at', 'invite_url', 'trips', 'no_trip']) {
      expect(body.containsKey(k), isFalse, reason: k);
    }
  });

  test('an interview create adds kind, test_at, invite_url and trips', () {
    final b = asInterview(
      _base(),
      testAt: DateTime(2026, 11, 20, 9, 5),
      inviteUrl: 'https://app.codility.com/c/acme',
      trips: const [(start: '2026-11-14', end: '2026-11-15')],
    );
    expect(b.kind, RequestKind.focusCreate);
    expect(b.body['kind'], 'interview');
    expect(b.body['test_at'], '2026-11-20T09:05');
    expect(b.body['invite_url'], 'https://app.codility.com/c/acme');
    expect(b.body['trips'], [
      {'start': '2026-11-14', 'end': '2026-11-15'},
    ]);
    expect(b.body.containsKey('no_trip'), isFalse);
    expect(b.body['name'], 'Acme', reason: 'base fields kept');
  });

  test('no trip is the explicit flag, never an empty list', () {
    final b = asInterview(
      _base(),
      testAt: DateTime(2026, 11, 20, 9),
      inviteUrl: '',
      noTrip: true,
    );
    expect(b.body['no_trip'], isTrue);
    expect(b.body.containsKey('trips'), isFalse);
  });

  test('trips XOR no_trip: neither or both is refused before sending', () {
    final at = DateTime(2026, 11, 20, 9);
    expect(
      () => asInterview(_base(), testAt: at, inviteUrl: ''),
      throwsArgumentError,
    );
    expect(
      () => asInterview(
        _base(),
        testAt: at,
        inviteUrl: '',
        noTrip: true,
        trips: const [(start: '2026-11-14', end: '2026-11-15')],
      ),
      throwsArgumentError,
    );
    expect(
      () => asInterview(
        _base(),
        testAt: at,
        inviteUrl: '',
        trips: [
          for (var i = 0; i < 21; i++) (start: '2026-11-14', end: '2026-11-15'),
        ],
      ),
      throwsArgumentError,
      reason: 'at most 20 trips',
    );
  });

  test('evidence bodies carry only what the milestone needs', () {
    expect(
      focusEvidence(id: 'p', milestone: 'phone:2026-11-14', kind: 'tap').body,
      {'id': 'p', 'milestone': 'phone:2026-11-14', 'kind': 'tap'},
    );
    expect(
      focusEvidence(
        id: 'p',
        milestone: 'mock',
        kind: 'score',
        value: 72.5,
      ).body['value'],
      72.5,
    );
    expect(
      focusEvidence(
        id: 'p',
        milestone: 'slot',
        kind: 'slot_confirm',
        value: true,
      ).body['value'],
      isTrue,
    );
    final file = focusEvidence(
      id: 'p',
      milestone: 'rules',
      kind: 'file',
      upload: (
        upload: '01HZZZZZZZZZZZZZZZZZZZZZZZ',
        chunks: 2,
        sha256: 'ab',
        mime: 'image/png',
      ),
    );
    expect(file.kind, RequestKind.focusEvidence);
    expect(file.body['upload'], '01HZZZZZZZZZZZZZZZZZZZZZZZ');
    expect(file.body['chunks'], 2);
    expect(file.body['sha256'], 'ab');
    expect(file.body['mime'], 'image/png');
    expect(file.body.containsKey('value'), isFalse);
  });

  test('trip and weekend bodies', () {
    final t = focusTrip('p', '2026-11-14', '2026-11-16');
    expect(t.kind, RequestKind.focusTrip);
    expect(t.body, {'id': 'p', 'start': '2026-11-14', 'end': '2026-11-16'});
    final w = focusWeekend('p', '2026-11-21', trip: false);
    expect(w.kind, RequestKind.focusWeekend);
    expect(w.body, {'id': 'p', 'saturday': '2026-11-21', 'trip': false});
  });
}
