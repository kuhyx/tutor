import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/config/firebase_config.dart';
import 'package:tutor/ui/app.dart';

// The entry point is the one line flutter_test cannot run; everything it
// builds is TutorApp / TutorServices, both tested.
// coverage:ignore-start
void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    TutorApp(
      config: FirebaseConfig.compiled,
      open: () => TutorServices.open(FirebaseConfig.compiled),
    ),
  );
}
// coverage:ignore-end
