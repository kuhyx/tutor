// Offline-first History (~/.claude/rules/offline-first.instructions.md):
// the list and every opened transcript are read from disk when the database
// is unreachable (also after a restart), and Archive lands locally at once
// and is pushed by itself once the database answers again.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/history_screen.dart';
import 'package:tutor/ui/transcript_screen.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/services.dart';
import '../support/ui.dart';

const _sid = '20261011-090000-a1b2';
const _old = 'tutor/v1-e2e/sessions/$_sid';

void main() {
  testWidgets('list and transcript read from disk offline and after restart', (
    t,
  ) async {
    final db = fixtureDb();
    db.root = setAt(db.root, '$_old/msgs', {
      'm0001': {'role': 'tutor', 'text': 'Earlier **turn**'},
    });
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, HistoryScreen(services: s));
    await pumpScreen(t, TranscriptScreen(services: s, sid: _sid));
    expect(find.textContaining('Earlier'), findsOneWidget);

    db.offline = true;
    // A restart: new services over the same disk.
    final again = services(db, stream, kv: s.kv);
    await pumpScreen(t, HistoryScreen(services: again));
    expect(find.textContaining('2026-10-11 09:00'), findsOneWidget);
    expect(cueOfKind(CueKind.offline), findsOneWidget);
    expect(cueOfKind(CueKind.error), findsNothing);

    await pumpScreen(t, TranscriptScreen(services: again, sid: _sid));
    expect(find.textContaining('Earlier'), findsOneWidget);
    expect(bySpoken('Read-only'), findsOneWidget);
    expect(cueOfKind(CueKind.offline), findsOneWidget);
  });

  testWidgets('archive offline shows at once and is pushed later', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, TranscriptScreen(services: s, sid: _sid));

    db.offline = true;
    await t.tap(controlByLabel('Archive'));
    await t.pumpAndSettle();
    expect(controlByLabel('Unarchive'), findsOneWidget);
    expect(getAt(db.root, '$_old/user/archived'), isNot(isTrue));

    // Still archived after a restart while offline.
    final again = services(db, stream, kv: s.kv);
    await pumpScreen(t, HistoryScreen(services: again));
    expect(find.textContaining('2026-10-11 09:00'), findsNothing);

    // Back online: the next Home load pushes it without any tap.
    db.offline = false;
    await again.home.load();
    expect(getAt(db.root, '$_old/user/archived'), isTrue);
    // The first run's waiting retry finds nothing left to push.
    await t.pump(const Duration(seconds: 5));
  });

  testWidgets('a failed archive push retries by itself', (t) async {
    final db = fixtureDb();
    final s = await fixtureServices(db, FakeStream());
    await pumpScreen(t, TranscriptScreen(services: s, sid: _sid));
    db.offline = true;
    await t.tap(controlByLabel('Archive'));
    await t.pumpAndSettle();
    db.offline = false;
    expect(getAt(db.root, '$_old/user/archived'), isNot(isTrue));
    await t.pump(const Duration(seconds: 5)); // the backoff's first wait
    await t.pumpAndSettle();
    expect(getAt(db.root, '$_old/user/archived'), isTrue);
  });
}
