import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/card.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/root.dart';
import 'package:tutor/model/session.dart';
import 'package:tutor/model/session_index.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/model/subject.dart';

import 'samples.dart' as s;

/// Through a real JSON encode/decode, like the wire.
Json _wire(Object v) => jsonDecode(jsonEncode(v)) as Json;

void _roundTrip(String name, Json sample, Json Function(Json) through) {
  test(name, () => expect(through(_wire(sample)), sample));
}

void main() {
  _roundTrip('meta', {
    'schema': 1,
    'min_client': 1,
  }, (j) => SchemaMeta.fromJson(j).toJson());
  _roundTrip('rev', {
    'catalog': 42,
    'stats': 7,
  }, (j) => Revs.fromJson(j).toJson());
  _roundTrip('live', {
    'session': '20261012-170448-5b71',
    'subject': 'car',
    'card': 'x',
    'since': 1,
  }, (j) => Live.fromJson(j).toJson());
  _roundTrip('prefs', {
    'current_subject': 'car',
  }, (j) => Prefs.fromJson(j).toJson());
  _roundTrip(
    'worker presence',
    s.worker,
    (j) => WorkerPresence.fromJson(j).toJson(),
  );
  _roundTrip('client presence', {
    'platform': 'android',
    'app': '1.0.0',
    'seen': 5,
  }, (j) => ClientPresence.fromJson(j).toJson());
  _roundTrip('stats', s.stats, (j) => Stats.fromJson(j).toJson());
  _roundTrip('feedback', {
    'category': 'response',
    'text': 't',
    'session': '20261012-170448-5b71',
    'msg': 'm0007',
    'dev': 'd',
    'at': 1,
    'route': '/session',
  }, (j) => Feedback.fromJson(j).toJson());
  _roundTrip('req', {
    'kind': 'message',
    'dev': 'd',
    'created': 1791731346100,
    'sent_at': 1791731346000,
    'body': {'session': '20261012-170448-5b71', 'text': '...'},
  }, (j) => RequestReq.fromJson(j).toJson());
  _roundTrip('claim', {
    'by': 'w',
    'lease_until': 9,
    'attempt': 1,
    'phase': 'thinking',
    'at': 3,
  }, (j) => RequestClaim.fromJson(j).toJson());
  _roundTrip('ok result', {
    'ok': true,
    'at': 1,
    'data': {'msg': 'm0012'},
  }, (j) => RequestResult.fromJson(j).toJson());
  _roundTrip('error result', {
    'ok': false,
    'at': 1,
    'code': 'not_live',
    'error': 'session is not live',
    'retry': false,
  }, (j) => RequestResult.fromJson(j).toJson());
  _roundTrip(
    'session meta',
    s.sessionMeta,
    (j) => SessionMeta.fromJson(j).toJson(),
  );
  _roundTrip('session user', {
    'archived': true,
  }, (j) => SessionUser.fromJson(j).toJson());
  _roundTrip(
    'tutor message',
    s.tutorMessage,
    (j) => Message.fromJson(j).toJson(),
  );
  _roundTrip(
    'learner message',
    s.learnerMessage,
    (j) => Message.fromJson(j).toJson(),
  );
  _roundTrip('card message', {
    'role': 'card',
    'text': 'f',
    'card_id': 'ld-y',
  }, (j) => Message.fromJson(j).toJson());
  _roundTrip('receipt', s.receipt, (j) => Receipt.fromJson(j).toJson());
  _roundTrip(
    'session index',
    s.indexRow,
    (j) => SessionIndexRow.fromJson(j).toJson(),
  );
  _roundTrip(
    'subject meta',
    s.subjectMeta,
    (j) => SubjectMeta.fromJson(j).toJson(),
  );
  _roundTrip('plan', s.plan, (j) => Plan.fromJson(j).toJson());
  _roundTrip('bare plan', {
    'rev': 1,
    'status': 'approved',
  }, (j) => Plan.fromJson(j).toJson());
  _roundTrip('card', s.card, (j) => StudyCard.fromJson(j).toJson());
  _roundTrip('concept', {
    'name': 'n',
    'at': 1,
    'card': 'ld-x',
    'session': '20261012-170448-5b71',
  }, (j) => Concept.fromJson(j).toJson());
  for (final event in [
    {
      'k': 'review',
      's': 'car',
      'c': 'eng',
      'r': 3,
      'at': 1,
      'rev': 1,
      'dur_ms': 5400,
    },
    {'k': 'flag', 's': 'car', 'c': 'eng', 'rev': 1, 'reason': 'wrong', 'at': 2},
    {'k': 'taught', 's': 'car', 'c': 'eng', 'at': 3, 'session': 'x'},
    {'k': 'untaught', 's': 'car', 'c': 'eng', 'at': 4},
  ]) {
    _roundTrip(
      'event ${event['k']}',
      event,
      (j) => LogEvent.fromJson(j).toJson(),
    );
  }
}
