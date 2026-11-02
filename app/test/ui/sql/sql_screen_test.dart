import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/sql/drill_screen.dart';
import 'package:tutor/ui/sql/sql_screen.dart';

import '../../sql/sql_fixtures.dart';
import '../../support/fake_rtdb.dart';
import '../../support/fake_stream.dart';
import '../../support/services.dart';
import '../../support/ui.dart';

void main() {
  late FakeRtdb db;
  late FakeStream stream;

  Future<void> open(WidgetTester t, {Map<String, Object?>? data}) async {
    db = FakeRtdb();
    stream = FakeStream();
    await pumpScreen(
      t,
      SqlPracticeScreen(services: services(db, stream)),
      settle: false,
    );
    expect(lastRequest(db).$2['kind'], 'sql_list');
    await answer(t, db, stream, data: data ?? listData);
  }

  testWidgets('groups drills under their topic', (t) async {
    await open(t);
    expect(find.text('basics'), findsOneWidget);
    expect(find.text('joins-null'), findsOneWidget);
    expect(find.text('Count rows'), findsOneWidget);
    expect(find.text('Left join gaps'), findsOneWidget);
    expect(find.byIcon(Icons.auto_awesome), findsOneWidget);
    expect(find.byIcon(Icons.visibility_outlined), findsOneWidget);
  });

  testWidgets('a drill outside the topic list still shows', (t) async {
    await open(
      t,
      data: {
        'topics': ['basics'],
        'drills': [
          {'id': 'x', 'title': 'Odd one', 'topic': 'dates', 'kind': 'write'},
        ],
      },
    );
    expect(find.text('dates'), findsOneWidget);
    expect(find.text('Odd one'), findsOneWidget);
  });

  testWidgets('a failed list shows the error with Retry', (t) async {
    db = FakeRtdb();
    stream = FakeStream();
    await pumpScreen(
      t,
      SqlPracticeScreen(services: services(db, stream)),
      settle: false,
    );
    await answer(
      t,
      db,
      stream,
      code: 'worker_error',
      error: 'docker down',
      extra: {'retry': true},
    );
    expect(find.text('Retry'), findsOneWidget);
  });

  testWidgets('tapping a drill opens it and asks for it', (t) async {
    await open(t);
    await t.tap(find.text('Count rows'));
    await t.pump();
    await t.pump(const Duration(milliseconds: 400));
    expect(find.byType(SqlDrillScreen), findsOneWidget);
    final (_, req) = lastRequest(db);
    expect(req['kind'], 'sql_get');
    expect((req['body'] as Map)['id'], 'basics-1');
  });

  testWidgets('New drill asks for the topic, then opens the drill', (t) async {
    await open(t);
    await t.tap(find.byKey(const ValueKey('new-drill-basics')));
    await t.pump(const Duration(milliseconds: 50));
    final (_, req) = lastRequest(db);
    expect(req['kind'], 'sql_generate');
    expect((req['body'] as Map)['topic'], 'basics');
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    await answer(
      t,
      db,
      stream,
      data: {
        'id': 'gen-10',
        'title': 'Fresh',
        'topic': 'basics',
        'kind': 'write',
        'source': 'generated',
      },
      settle: false,
    );
    await t.pump(const Duration(milliseconds: 400));
    expect(find.byType(SqlDrillScreen), findsOneWidget);
    expect((lastRequest(db).$2['body'] as Map)['id'], 'gen-10');
  });
}
