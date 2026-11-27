// The worker's `unchecked` / `checked` events survive a JSON round trip.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/log_event.dart';

void main() {
  test('unchecked keeps its source; checked has none', () {
    final wire = [
      {'k': 'unchecked', 's': 'car', 'c': 'a-1', 'at': 5, 'src': 'read'},
      {'k': 'checked', 's': 'car', 'c': 'a-1', 'at': 6},
    ];
    for (final json in wire) {
      final event = LogEvent.fromJson(json);
      expect(event, isA<CheckMarkEvent>());
      expect(event.toJson(), json);
    }
  });
}
