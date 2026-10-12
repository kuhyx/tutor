import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/config/firebase_config.dart';
import 'package:tutor/storage/kv_open.dart';
import 'package:tutor/ui/app.dart';
import 'package:tutor/ui/ui_zoom.dart';

// The entry point is the one line flutter_test cannot run; everything it
// builds is TutorApp / TutorServices, both tested.
// coverage:ignore-start
void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // Loaded beside the services, not inside them: the zoom applies from the
  // sign-in screen on.
  final zoom = UiZoom();
  unawaited(zoom.load(openKv()));
  runApp(
    TutorApp(
      config: FirebaseConfig.compiled,
      open: () => TutorServices.open(
        FirebaseConfig.compiled,
        // The desktop (web) build adopts the PC's session from its server.
        wrapperBase: kIsWeb ? Uri.base : null,
      ),
      zoom: zoom,
    ),
  );
}
// coverage:ignore-end
