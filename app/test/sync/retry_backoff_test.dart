// A failed sync push retries by itself, waiting longer each time.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/retry_backoff.dart';

void main() {
  test(
    'one timer at a time, doubling, reset by a push that got through',
    () async {
      var runs = 0;
      final b = RetryBackoff(
        () async => runs++,
        first: const Duration(milliseconds: 10),
      )
        ..failed()
        ..failed(); // already waiting: no second timer
      expect(b.armed, isTrue);
      expect(b.wait, const Duration(milliseconds: 20));
      await Future<void>.delayed(const Duration(milliseconds: 40));
      expect(runs, 1);
      expect(b.armed, isFalse);
      b
        ..failed()
        ..ok();
      expect(b.armed, isFalse);
      expect(b.wait, const Duration(milliseconds: 10));
      await Future<void>.delayed(const Duration(milliseconds: 30));
      expect(runs, 1);
    },
  );

  test('the wait stops growing at kMaxRetry', () {
    final b = RetryBackoff(() async => null, first: const Duration(minutes: 4))
      ..failed();
    expect(b.wait, kMaxRetry);
    b.dispose();
  });
}
