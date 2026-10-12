import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/util/refresher.dart';

void main() {
  test('keeps the last value while reloading and after a failure', () async {
    var next = Future<int?>.value(1);
    final r = Refresher<int?>(() => next);
    var notified = 0;
    r.addListener(() => notified++);
    expect(r.hasData, isFalse);
    await r.reload();
    expect((r.hasData, r.data, r.loading, r.error), (true, 1, false, null));
    final gate = Completer<int?>();
    next = gate.future;
    final pending = r.reload();
    expect((r.loading, r.data), (true, 1)); // still on screen
    gate.completeError(StateError('down'));
    await pending;
    expect((r.data, r.loading), (1, false));
    expect(r.error, isA<StateError>());
    next = Future.value();
    await r.reload();
    expect((r.hasData, r.data, r.error), (true, null, null)); // loaded null
    expect(notified, 6);
    r.dispose();
  });

  test('an older reload never overwrites a newer one', () async {
    final slow = Completer<int>();
    final fail = Completer<int>();
    final queue = [slow.future, fail.future, Future.value(3)];
    final r = Refresher<int>(() => queue.removeAt(0));
    final a = r.reload();
    final b = r.reload();
    await r.reload();
    slow.complete(1);
    fail.completeError(StateError('late'));
    await a;
    await b;
    expect((r.data, r.error), (3, null));
    r.dispose();
  });

  test('hold parks a value until applied; force skips it', () async {
    var value = 1;
    var dirty = false;
    final r = Refresher<int>(
      () async => value,
      hold: (now, next) => dirty && now != next,
    );
    await r.reload();
    dirty = true;
    value = 2;
    await r.reload();
    expect((r.data, r.hasPending, r.resets), (1, true, 0));
    value = 1;
    await r.reload(); // same as on screen: not held, pending dropped
    expect((r.data, r.hasPending), (1, false));
    value = 3;
    await r.reload();
    r.applyPending();
    expect((r.data, r.hasPending, r.resets), (3, false, 1));
    r.applyPending(); // nothing pending: no-op
    expect(r.resets, 1);
    value = 4;
    await r.reload(force: true);
    expect((r.data, r.resets), (4, 2));
    r.dispose();
    await r.reload(); // after dispose: no notify, no throw
  });
}
