/// Drill test helpers: reply payloads, a raw relay answer and a fake
/// AnkiDroid launcher.
library;

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/drill/anki_sync.dart';
import 'package:tutor/sync/rtdb_event.dart';

import 'fake_rtdb.dart';
import 'fake_stream.dart';
import 'ui.dart';

/// A phone-sized window (1080x2400 at 2.625x).
const kPhone = Size(412, 915);

/// A `resets_at` for the Claude-out tests (unix seconds).
const kResetsAt = 1792000000;

/// Local HH:MM of [unixSeconds], as the banner shows it.
String hhmm(int unixSeconds) {
  final t = DateTime.fromMillisecondsSinceEpoch(unixSeconds * 1000);
  return '${t.hour.toString().padLeft(2, '0')}:'
      '${t.minute.toString().padLeft(2, '0')}';
}

/// A `drill_next` question; [unavailable] adds the Claude-out marker.
Map<String, Object?> drillQuestion({
  String front = 'What does the crankshaft do?',
  Map<String, Object?>? unavailable,
}) => {
  'prompt_id': 'p1',
  'card': {'subject': 'car', 'id': 'eng-crank', 'front': front},
  'options': ['Opens valves', 'Turns pistons into rotation', 'Mixes fuel'],
  'today': {'active_min': 31, 'credited_min': 23},
  'unavailable': ?unavailable,
};

/// A `drill_answer` result for a pick of option [choice] (right: 1).
Map<String, Object?> drillGrade(int choice) => {
  'correct': choice == 1,
  'answer_index': 1,
  'back': 'It turns the pistons’ motion into rotation.',
  'excerpt': 'The crankshaft translates reciprocating motion.',
  'source': 'https://en.wikipedia.org/wiki/Crankshaft',
  'minute_credited': choice == 1,
  'today': {'active_min': 32, 'credited_min': choice == 1 ? 24 : 23},
};

/// An `anki_status` result.
Map<String, Object?> ankiStatus(int credited) => {
  'credited_today_min': credited,
  'eligible_today_min': 12,
};

/// Answers the latest request with a whole `result` node (error bodies).
Future<void> reply(
  WidgetTester tester,
  FakeRtdb db,
  FakeStream stream,
  Map<String, Object?> result, {
  bool settle = true,
}) async {
  final (rid, _) = lastRequest(db);
  stream.emit('tutor/v1/requests/$rid', RtdbPut('/', {'result': result}));
  settle ? await tester.pumpAndSettle() : await sent(tester);
}

/// Records the launches; answers [ok].
class FakeLauncher implements AnkiLauncher {
  /// Creates the launcher.
  new({this.supported = true, this.ok = true});

  @override
  final bool supported;

  /// What [sync] reports.
  final bool ok;

  /// How often the intent was fired.
  int launches = 0;

  @override
  Future<bool> sync() async {
    launches++;
    return ok;
  }
}
