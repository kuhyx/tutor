import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/feedback/feedback_sender.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/util/ulid.dart';

import '../support/fake_rtdb.dart';

void main() {
  test('writes one report under feedback/{fid}', () async {
    final db = FakeRtdb();
    final sender = FeedbackSender(
      client: db.client(),
      dev: '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10',
      ulid: UlidGenerator(),
      now: () => 42,
    );
    final fid = await sender.send(
      category: FeedbackCategory.response,
      text: '  same image twice ',
      route: '/session',
      session: '20261012-170448-5b71',
      msg: 'm0007',
    );
    final node = getAt(db.root, 'tutor/v1/feedback/$fid')! as Map;
    expect(node['text'], 'same image twice');
    expect(node['category'], 'response');
    expect(node['at'], 42);
    expect(node['msg'], 'm0007');
    expect(
      () => sender.send(category: FeedbackCategory.ui, text: ' ', route: '/'),
      throwsArgumentError,
    );
    final real = FeedbackSender(
      client: db.client(),
      dev: 'd',
      ulid: UlidGenerator(),
    );
    final id = await real.send(
      category: FeedbackCategory.ui,
      text: 'x',
      route: '/',
    );
    expect((getAt(db.root, 'tutor/v1/feedback/$id')! as Map)['at'], isPositive);
  });
}
