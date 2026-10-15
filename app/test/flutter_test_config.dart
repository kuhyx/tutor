// flutter_test reports Android as the platform, so every test would be the
// phone. The suite's baseline is the desktop (web) build; phone tests turn
// `debugPhone` on and reset it with addTearDown.
import 'dart:async';

import 'package:tutor/util/device.dart';

Future<void> testExecutable(FutureOr<void> Function() testMain) async {
  debugPhone = false;
  await testMain();
}
