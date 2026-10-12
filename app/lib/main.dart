import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

// coverage:ignore-line
void main() => runApp(const TutorApp());

/// Root widget.
class TutorApp extends StatelessWidget {
  /// Creates the app.
  const new({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Tutor',
    theme: buildLightTheme(),
    darkTheme: buildDarkTheme(),
    home: const Scaffold(body: Center(child: Text('Tutor'))),
  );
}
