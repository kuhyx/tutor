import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/model/root.dart';
import 'package:tutor/session/session_entry.dart';

const _car = Live(session: '20261012-195411-37f4', subject: 'how-a-car-works');

void main() {
  test('no subject picked: whatever is live, or Learn', () {
    final none = sessionEntry(null, null);
    expect(
      (none.kind, none.subject, none.resume),
      (SessionKind.learn, null, false),
    );
    final live = sessionEntry(_car, null);
    expect(
      (live.kind, live.subject, live.resume),
      (SessionKind.live, null, false),
    );
  });

  test('the live session is of the picked subject: continue it', () {
    final e = sessionEntry(_car, 'how-a-car-works');
    expect(
      (e.kind, e.subject, e.resume),
      (SessionKind.live, 'how-a-car-works', false),
    );
  });

  test('another subject is live: ask for the picked one, never follow it', () {
    // kuhy, 2026-10-12: in automation, Continue opened the car session.
    for (final live in [_car, null]) {
      final e = sessionEntry(live, 'automation');
      expect(
        (e.kind, e.subject, e.resume),
        (SessionKind.resume, 'automation', true),
      );
    }
  });

  test('the spoken labels are the old button words', () {
    expect(sessionEntry(null, null).semanticLabel, 'Learn');
    expect(sessionEntry(_car, null).semanticLabel, 'Continue session');
    expect(sessionEntry(null, 'x').semanticLabel, 'Continue learning');
  });

  test('session_start carries resume only when asked', () {
    expect(RequestBody.sessionStart(subject: 'automation').body, {
      'subject': 'automation',
      'card': null,
    });
    expect(RequestBody.sessionStart(subject: 'automation', resume: true).body, {
      'subject': 'automation',
      'card': null,
      'resume': true,
    });
  });
}
