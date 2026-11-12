// The Session screen shows `sessions/{sid}/progress` (from its one session
// listen) while a turn is in flight (only the busy request's), and the
// reply keeps its trace folded.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

const _base = 'tutor/v1-e2e/sessions/$fixtureLiveSid';
const _rid = '01M4RBCX52MMHCK7K73E6KV910';

void main() {
  testWidgets('progress streams live under the busy line', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, SessionScreen(services: s), settle: false);
    for (final path in ['tutor/v1-e2e/live', '$_base/meta', '$_base/msgs']) {
      stream.emit(path, RtdbPut('/', getAt(db.root, path)));
      await t.pump();
    }
    void meta(RtdbEvent e) => stream.emit('$_base/meta', e);
    void progress(RtdbEvent e) => stream.emit('$_base/progress', e);
    meta(
      const RtdbPatch('/', {
        'busy': {'rid': _rid, 'phase': 'thinking', 'since': 1, 'text': 'hi'},
      }),
    );
    // Another request's leftovers are not this turn's.
    progress(
      const RtdbPut('/', {
        'rid': 'OTHER',
        'steps': {
          's0001': {'kind': 'tool', 'name': 'WebSearch', 'input': 'stale'},
        },
      }),
    );
    await t.pump();
    expect(bySpoken('Tutor is thinking...'), findsOneWidget);
    expect(find.text('stale'), findsNothing);

    progress(
      const RtdbPut('/', {
        'rid': _rid,
        'steps': {
          's0001': {'kind': 'thinking', 'text': 'Plan the next ask.'},
        },
      }),
    );
    progress(
      const RtdbPatch('/steps', {
        's0002': {'kind': 'tool', 'name': 'WebSearch', 'input': 'four stroke'},
      }),
    );
    await t.pump();
    expect(bySpoken('Researching...'), findsOneWidget);
    expect(find.text('four stroke'), findsOneWidget);
    expect(find.text('Plan the next ask.'), findsNothing);
    await t.tap(bySpoken('Thinking · 1 research step'));
    await t.pump();
    expect(find.text('Plan the next ask.'), findsOneWidget);

    // The reply lands: busy and progress go, the bubble has it folded.
    meta(const RtdbPatch('/', {'busy': null}));
    progress(const RtdbPut('/', null));
    stream.emit(
      '$_base/msgs',
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
    expect(bySpoken('Researching...'), findsNothing);
    expect(bySpoken('Thinking · 1 research step'), findsOneWidget);
    expect(find.text('Plan the next ask.'), findsNothing);
  });

  testWidgets('a follow-up at card end shows its research live too', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, SessionScreen(services: s), settle: false);
    for (final path in ['tutor/v1-e2e/live', '$_base/meta', '$_base/msgs']) {
      stream.emit(path, RtdbPut('/', getAt(db.root, path)));
      await t.pump();
    }
    stream
      ..emit(
        '$_base/meta',
        const RtdbPatch('/', {
          'card_done': true,
          'busy': {
            'rid': _rid,
            'phase': 'thinking',
            'since': 1,
            'text': 'why?',
          },
        }),
      )
      ..emit(
        '$_base/progress',
        const RtdbPut('/', {
          'rid': _rid,
          'steps': {
            's0001': {'kind': 'tool', 'name': 'WebSearch', 'input': 'why coil'},
          },
        }),
      );
    await t.pump();
    expect(controlByLabel('Next card'), findsOneWidget);
    expect(bySpoken('Researching...'), findsOneWidget);
    expect(find.text('why coil'), findsOneWidget);
  });
}
