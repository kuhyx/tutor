/// Read-mode test helpers: `read_next` / `read_rate` reply payloads.
library;

/// A `read_next` card; [unavailable] adds the Claude-out window.
Map<String, Object?> readCard({
  String id = 'eng-crank',
  String front = 'What does the crankshaft do?',
  String back = 'It turns the pistons’ motion into rotation.',
  String excerpt = 'The crankshaft translates reciprocating motion.',
  Map<String, Object?>? unavailable,
}) => {
  'prompt_id': readPromptId(id),
  'card': {
    'subject': 'car',
    'id': id,
    'module': 'engine',
    'front': front,
    'back': back,
    'excerpt': excerpt,
    'source': 'https://en.wikipedia.org/wiki/Crankshaft',
  },
  'today': {'active_min': 3, 'credited_min': 2},
  'unavailable': unavailable,
};

/// The prompt id [readCard] sends for card [id].
String readPromptId([String id = 'eng-crank']) => 'p-$id';

/// A `read_rate` result.
Map<String, Object?> readRated(String rating, {bool credited = false}) => {
  'rated': rating,
  'minute_credited': credited,
  'today': {'active_min': 4, 'credited_min': credited ? 3 : 2},
};
