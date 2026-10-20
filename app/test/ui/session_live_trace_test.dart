// The Session screen follows `sessions/{sid}/progress` while a turn is in
// flight (only the busy request's), and the reply keeps its trace folded.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/fake_stream.dart';
import '../support/ui.dart';

const _base = 'tutor/v1/sessions/$fixtureLiveSid';
const _rid = '01M4RBCX52MMHCK7K73E6KV910';

void main() {
  testWidgets('progress streams live under the busy line', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, SessionScreen(services: s), settle: false);
    for (final path in ['tutor/v1/live', '$_base/meta', '$_base/msgs']) {
      stream.listens[path]?.add(RtdbPut('/', getAt(db.root, path)));
      await t.pump();
    }
    final meta = stream.listens['$_base/meta']!;
    final progress = stream.listens['$_base/progress']!;
    meta.add(
      const RtdbPatch('/', {
        'busy': {'rid': _rid, 'phase': 'thinking', 'since': 1, 'text': 'hi'},
      }),
    );
    // Another request's leftovers are not this turn's.
    progress.add(
      const RtdbPut('/', {
        'rid': 'OTHER',
        'steps': {
          's0001': {'kind': 'tool', 'name': 'WebSearch', 'input': 'stale'},
        },
      }),
    );
    await t.pump();
    expect(find.text('Tutor is thinking...'), findsOneWidget);
    expect(find.text('Search: stale'), findsNothing);

    progress
      ..add(
        const RtdbPut('/', {
          'rid': _rid,
          'steps': {
            's0001': {'kind': 'thinking', 'text': 'Plan the next ask.'},
          },
        }),
      )
      ..add(
        const RtdbPatch('/steps', {
          's0002': {
            'kind': 'tool',
            'name': 'WebSearch',
            'input': 'four stroke',
          },
        }),
      );
    await t.pump();
    expect(find.text('Researching...'), findsOneWidget);
    expect(find.text('Search: four stroke'), findsOneWidget);
    expect(find.text('Plan the next ask.'), findsNothing);
    await t.tap(find.text('Thinking · 1 research step'));
    await t.pump();
    expect(find.text('Plan the next ask.'), findsOneWidget);

    // The reply lands: busy and progress go, the bubble has it folded.
    meta.add(const RtdbPatch('/', {'busy': null}));
    progress.add(const RtdbPut('/', null));
    stream.listens['$_base/msgs']!.add(
      const RtdbPatch('/', {
        'm0005': {
          'role': 'tutor',
          'text': 'Which stroke makes the power?',
          'trace': [
            {'kind': 'thinking', 'text': 'Plan the next ask.'},
            {'kind': 'tool', 'name': 'WebSearch', 'input': 'four stroke'},
          ],
        },
      }),
    );
    await t.pump();
    expect(find.text('Researching...'), findsNothing);
    expect(find.text('Thinking · 1 research step'), findsOneWidget);
    expect(find.text('Plan the next ask.'), findsNothing);
  });

  testWidgets('a follow-up at card end shows its research live too', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, SessionScreen(services: s), settle: false);
    for (final path in ['tutor/v1/live', '$_base/meta', '$_base/msgs']) {
      stream.listens[path]?.add(RtdbPut('/', getAt(db.root, path)));
      await t.pump();
    }
    stream.listens['$_base/meta']!.add(
      const RtdbPatch('/', {
        'card_done': true,
        'busy': {'rid': _rid, 'phase': 'thinking', 'since': 1, 'text': 'why?'},
      }),
    );
    stream.listens['$_base/progress']!.add(
      const RtdbPut('/', {
        'rid': _rid,
        'steps': {
          's0001': {'kind': 'tool', 'name': 'WebSearch', 'input': 'why coil'},
        },
      }),
    );
    await t.pump();
    expect(find.text('Next card'), findsOneWidget);
    expect(find.text('Researching...'), findsOneWidget);
    expect(find.text('Search: why coil'), findsOneWidget);
  });
}
