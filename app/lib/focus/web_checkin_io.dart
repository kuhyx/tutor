/// The non-web half of `web_checkin.dart`: no browser, no notification.
library;

import 'package:tutor/focus/checkin_notifier.dart';

/// The browser notifier does not exist off the web; Android wires its own.
FocusCheckinNotifier createWebCheckinNotifier() => const NoopCheckinNotifier();
