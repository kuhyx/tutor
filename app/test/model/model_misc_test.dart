import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/model/root.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/model/subject.dart';

const _dev = '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10';
const _rid = '01JABCDEFGHJKMNPQRSTVWXYZ0';

void main() {
  group('json helpers', () {
    test('wrong types name the field', () {
      expect(() => str({'a': 1}, 'a'), throwsFormatException);
      expect(() => integer({'a': 'x'}, 'a'), throwsFormatException);
      expect(() => dbl({}, 'a'), throwsFormatException);
      expect(() => flag({'a': 1}, 'a'), throwsFormatException);
      expect(() => asJson(3), throwsFormatException);
      expect(() => strings({'a': 'x'}, 'a'), throwsFormatException);
      expect(
        () => strings({
          'a': [1],
        }, 'a'),
        throwsFormatException,
      );
      expect(
        () => byWire(Lane.values, 'x', (l) => l.name),
        throwsFormatException,
      );
    });

    test('absent optional values', () {
      expect(dblOr({}, 'a'), isNull);
      expect(intOr({'a': 2.0}, 'a'), 2);
      expect(flag({}, 'a', fallback: true), isTrue);
      expect(mapOf({}, 'a', (v) => v), isEmpty);
      expect(compact({'a': null, 'b': 1}), {'b': 1});
    });
  });

  group('ids and paths', () {
    test('formats', () {
      expect(isSlug('engine-basics'), isTrue);
      expect(isSlug('Engine'), isFalse);
      expect(isSlug('a' * 49), isFalse);
      expect(isUlid(_rid), isTrue);
      expect(isUlid('01JABCDEFGHJKMNPQRSTVWXYZU'), isFalse);
      expect(isSessionId('20261012-170448-5b71'), isTrue);
      expect(isMessageKey('m0007'), isTrue);
      expect(isMessageKey('7'), isFalse);
      expect(isReceiptKey('r0003'), isTrue);
      expect(messageKey(12), 'm0012');
      expect(isDeviceId(_dev), isTrue);
      expect(isDeviceId('pc'), isFalse);
    });

    test('paths validate every segment', () {
      expect(Paths.requestReq(_rid), 'tutor/v1/requests/$_rid/req');
      expect(Paths.client(_dev), 'tutor/v1/presence/clients/$_dev');
      expect(Paths.subject('car'), 'tutor/v1/subjects/car');
      expect(
        Paths.session('20261012-170448-5b71'),
        'tutor/v1/sessions/20261012-170448-5b71',
      );
      expect(Paths.logEvent(_dev, _rid), 'tutor/v1/log/$_dev/$_rid');
      expect(Paths.feedback(_rid), 'tutor/v1/feedback/$_rid');
      expect(() => Paths.subject('../x'), throwsArgumentError);
      expect(() => Paths.logOf('phone'), throwsArgumentError);
    });
  });

  group('records', () {
    test('schema gate', () {
      const m = SchemaMeta(schema: 1, minClient: 2);
      expect(m.allows(knownSchema: 1, clientVersion: 2), isTrue);
      expect(m.allows(knownSchema: 1, clientVersion: 1), isFalse);
      expect(m.allows(knownSchema: 2, clientVersion: 9), isFalse);
    });

    test('client-written timestamps default to the server value', () {
      const p = ClientPresence(platform: 'web', app: '1');
      expect(p.toJson()['seen'], serverTimestamp);
      final req = RequestReq(
        kind: RequestKind.stop,
        dev: _dev,
        sentAt: 1,
        body: RequestBody.stop('20261012-170448-5b71').body,
      );
      expect(req.toJson()['created'], {'.sv': 'timestamp'});
      expect(Revs.fromJson({}).catalog, 0);
    });

    test('enums parse by wire name', () {
      expect(RequestKind.parse('subject_new').lane, Lane.build);
      expect(RequestKind.parse('message').lane, Lane.chat);
      expect(Phase.parse('checking_images'), Phase.checkingImages);
      expect(SubjectStatus.parse('review_only'), SubjectStatus.reviewOnly);
      expect(() => ModuleStatus.parse('x'), throwsFormatException);
      expect(() => Grade.parse(5), throwsFormatException);
    });

    test('image allowlist and stalled clock', () {
      const img = Img(
        url: 'https://evil.example/x.jpg',
        title: 't',
        author: 'a',
        licence: 'l',
        pageUrl: 'p',
      );
      expect(img.loadable, isFalse);
      final thumb = Img.fromJson({
        'url': 'https://thumb.wikimedia.org/a/960px-b.jpg',
        'title': 't',
        'author': 'a',
        'licence': 'l',
        'page_url': 'p',
      });
      expect(thumb.loadable, isTrue);
      final none = Img.fromJson({
        'title': 't',
        'author': 'a',
        'licence': 'l',
        'page_url': 'p',
      });
      expect(none.loadable, isFalse);
      expect(none.toJson().containsKey('url'), isFalse);
      const clock = EngagementClock(
        activeSeconds: 1,
        replyTimeoutS: 600,
        awaitingSince: 0,
      );
      expect(clock.stalledAt(600 * 1000), isFalse);
      expect(clock.stalledAt(600 * 1000 + 1), isTrue);
      expect(
        const EngagementClock(
          activeSeconds: 0,
          replyTimeoutS: 600,
        ).stalledAt(1 << 40),
        isFalse,
      );
    });

    test('defaults for sparse records', () {
      final m = Module.fromJson({'id': 'a', 'title': 'A'});
      expect(m.status, ModuleStatus.locked);
      expect(m.toJson(), {
        'id': 'a',
        'title': 'A',
        'summary': '',
        'depth': 1,
        'status': 'locked',
        'recall': 0.0,
        'cards': 0,
      });
      final meta = SubjectMeta.fromJson({
        'title': 't',
        'status': 'draft',
        'created': 1,
        'rev': 1,
        'origin': 'seed',
      });
      expect(meta.toJson().containsKey('goal'), isFalse);
      final flagEvent = LogEvent.fromJson({
        'k': 'flag',
        's': 'a',
        'c': 'b',
        'rev': 1,
        'at': 1,
      }) as FlagEvent;
      expect(flagEvent.reason, '');
      expect(flagEvent.key, 'a/b');
      expect(
        () => LogEvent.fromJson({'k': 'x', 's': 'a', 'c': 'b', 'at': 1}),
        throwsFormatException,
      );
      final logged = LoggedEvent(dev: _dev, eid: _rid, event: flagEvent);
      expect(logged.event, same(flagEvent));
    });
  });

  group('request bodies', () {
    test('every kind builds its contract body', () {
      const m = Module(id: 'a', title: 'A');
      final all = [
        RequestBody.subjectNew('learn cars'),
        RequestBody.planRevise('car', 3, 'less history'),
        RequestBody.planEdit('car', 3, const [m]),
        RequestBody.planApprove('car', 4),
        RequestBody.subjectFinish('car', goDeeper: true),
        RequestBody.subjectFinish('car', goDeeper: false),
        RequestBody.cardEdit(
          subject: 'car',
          module: 'a',
          front: 'f',
          back: 'b',
          source: 'https://x',
          excerpt: 'e',
        ),
        RequestBody.sessionStart(subject: 'car'),
        RequestBody.sessionResume('s'),
        RequestBody.message('s', 'hi'),
        RequestBody.next('s'),
        RequestBody.stop('s'),
        RequestBody.cardDone('car', 'x'),
      ];
      expect(all.map((b) => b.kind.wire).toSet(), hasLength(12));
      expect(all[2].body['modules'], [m.toJson()]);
      expect(all[4].body['choice'], 'go_deeper');
      expect(all[5].body['choice'], 'review_only');
      expect(all[6].body['card'], isNull);
      expect(all.last.body['done'], isTrue);
    });

    test('oversize text is refused before sending', () {
      expect(() => RequestBody.subjectNew('x' * 2001), throwsArgumentError);
      expect(() => RequestBody.message('s', 'x' * 8001), throwsArgumentError);
    });
  });
}
